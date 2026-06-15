"""数据来源标注硬规则后处理。

在 LLM 输出后，自动检测未带来源标注的具体数字，
按 zhangxuefeng-skill-merged 的 6 条来源标注硬规则补全。

设计原则（来自 zhangxuefeng-skill-merged SKILL.md:196-207）：
- 录取分数线/位次
- 薪资数据
- 就业率
- 行业数据
- 未交叉验证的数据
- 训练语料推断的数据
"""

from __future__ import annotations

import re

# 匹配"具体数字 + 单位"的模式
# 例: "580分", "3000元/月", "85%", "1万位次", "5-8万", "985院校"
_NUMBER_WITH_UNIT = re.compile(
    r"(\d[\d,\.\- ～~]*\d|\d)\s*"  # 数字（含小数/范围/千分位）
    r"(分|位次|%|元/月|元/年|万|亿|千|公里|亩|平方米|平米|㎡)"
    r"(?![元/月年所人个倍万分亿千])",  # 负向预查：避免重复匹配单位
    re.UNICODE,
)
# 人数类匹配:严格白名单,避免"985人""211人"等教育标识误触
_NUMBER_PEOPLE = re.compile(
    r"(?<![一-鿿])\d{2,}\s*"  # 至少 2 位数字,前面不是中文
    r"(?:位同学|位学生|名学生|位家长|个家庭)"
)

# 教育标识(985/211/双一流/985工程/211工程)用于豁免"人""个"等单位
_EDUCATION_BADGE = re.compile(r"(985|211|双一流|一本|二本|三本|985工程|211工程)")

# 已带来源的标记（LLM 可能输出的格式）
_SOURCE_MARKERS = [
    "来源",
    "数据来源",
    "出处",
    "根据",
    "数据显示",
    "考试院",
    "阳光高考",
    "就业质量报告",
    "招聘平台",
    "据",
    "官网",
    "教育部",
    "统计局",
]

# 不需要来源的"安全数字"模式（句首问候/场景化数字）
_SAFE_NUMBER_PATTERNS = [
    re.compile(r"^第\s*\d+"),  # 第N
    re.compile(r"^\d{4}年"),  # 2024年 (年号)
    re.compile(r"^\d+[、.]"),  # 1、2. (列表序号)
    re.compile(r"^\d{1,2}月"),  # 6月
    re.compile(r"^20\d{2}[-/]\d{1,2}"),  # 2024-01
    re.compile(r"^\d+:\d{2}"),  # 12:30
    re.compile(r"^[一二三四五六七八九十]+"),  # 中文数字
]


def _has_source_marker(sentence: str) -> bool:
    """检查句子是否已包含来源标记。"""
    return any(m in sentence for m in _SOURCE_MARKERS)


def _is_safe_number(sentence: str, match: re.Match) -> bool:
    """检查匹配到的数字是否属于"安全"（不需要来源）。"""
    matched_text = match.group(0)
    # 句首的非数据型数字不需要来源
    if sentence.lstrip().startswith(matched_text):
        for safe_pat in _SAFE_NUMBER_PATTERNS:
            if safe_pat.match(matched_text):
                return True
    # 教育标识(985/211/双一流等)后面的"人"等不算数据需求
    if _EDUCATION_BADGE.search(sentence) and any(kw in matched_text for kw in ("人", "个", "所", "位")):
        return True
    return False


def _has_unattributed_data(sentence: str) -> bool:
    """综合判断:句中是否含未带来源的具体数据数字。"""
    match = _NUMBER_WITH_UNIT.search(sentence)
    if not match:
        return False
    if _is_safe_number(sentence, match):
        return False
    return True


def validate_source_attribution(reply: str) -> str:
    """检测回复中无来源标注的具体数字，自动追加警告。

    Args:
        reply: LLM 输出的回复文本

    Returns:
        处理后的回复（无来源的具体数字会被追加「（数据来源待补全）」）
    """
    if not reply:
        return reply

    # 按句子切分（保留标点）
    sentences = re.split(r"(?<=[。！？\n])", reply)
    annotated: list[str] = []
    for sent in sentences:
        if not sent.strip():
            annotated.append(sent)
            continue
        # 已经是声明/免责声明就不处理
        if sent.strip().startswith("声明") or sent.strip().startswith("---"):
            annotated.append(sent)
            continue
        # 如果已带来源标记，跳过
        if _has_source_marker(sent):
            annotated.append(sent)
            continue
        # 综合判定：是否有未带来源的具体数据
        if _has_unattributed_data(sent):
            stripped = sent.rstrip()
            if stripped and stripped[-1] in "。！？\n":
                stripped = stripped[:-1]
            annotated.append(f"{stripped}（数据来源待补全）。")
        else:
            annotated.append(sent)

    return "".join(annotated)
