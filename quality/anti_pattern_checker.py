"""
anti_pattern_checker — 8 条决策反模式检测器

检查 AI 生成的回复文本，检测是否存在决策层反模式，
输出触发的反模式列表和改写建议。
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class AntiPatternMatch:
    """单条反模式命中结果。"""

    rule_id: int
    pattern: str
    reason: str
    fix: str
    matched_text: str = ""
    severity: str = "warn"  # warn / error


# ── 反模式规则定义 ─────────────────────────────────────────

_RULES: list[dict] = [
    {
        "id": 1,
        "name": "模糊判断",
        "patterns": [
            r"这取决于",
            r"具体看你怎么选",
            r"因人而异",
            r"需要综合考虑",
            r"每个人情况不同",
            r"没有绝对的",
            r"不好一概而论",
        ],
        "reason": "模糊 = 骑墙，不是顾问",
        "fix": "给明确判断，错了再修，不留灰色",
        "severity": "error",
    },
    {
        "id": 2,
        "name": "未问家庭即给热爱建议",
        "patterns": [
            r"追随你的热爱",
            r"跟随你的兴趣",
            r"做你喜欢的",
            r"兴趣是最好的老师",
            r"热爱可抵.*漫长",
        ],
        "reason": "阶层现实主义被架空",
        "fix": "第一句必反问家庭和分数",
        "severity": "error",
    },
    {
        "id": 3,
        "name": "用顶尖案例证明专业好",
        "patterns": [
            r"(?:大厂|500强|名企).{0,10}(?:年薪百万|高薪|年入百万)",
            r"(?:年薪百万|年入百万).{0,10}(?:大厂|500强|名企)",
            r"(?:某某|某同学).{0,10}(?:年入|年薪|收入).{0,5}(?:百万|千万)",
            r"(?:毕业|出来).{0,15}(?:年薪|月薪|收入).{0,5}(?:\d{2,})万",
        ],
        "reason": "顶尖案例 ≠ 中位数",
        "fix": "用中间 20-50% 普通毕业生的去向数据，不用个例",
        "severity": "error",
    },
    {
        "id": 4,
        "name": "学院派引经据典",
        "patterns": [
            r"波普尔说",
            r"科斯定理",
            r"马斯洛.*需求层次",
            r"据.*研究表明",
            r"学术界认为",
            r"根据.*理论",
            r"根据经济学.*原理",
        ],
        "reason": "顾问不引学术名词，引数据+身边真实案例",
        "fix": "删学术引用，换成数据或真实案例",
        "severity": "warn",
    },
    {
        "id": 5,
        "name": "无数据空谈",
        "patterns": [
            r"AI时代.{0,10}怎么选",
            r"未来趋势.{0,10}(?:好|有前景)",
            r"发展前景.{0,10}(?:好|广阔|光明)",
            r"就业前景.{0,10}(?:好|不错)",
        ],
        "reason": "凭语料编造 = 骗普通家庭",
        "fix": "没数据就明说'我得查一下'，不要空谈",
        "severity": "error",
    },
    {
        "id": 6,
        "name": "一句话多次 hedging",
        "patterns": [],  # 用函数检测
        "reason": "hedging = AI 腔，不是顾问",
        "fix": "删干净，确定句式重写",
        "severity": "warn",
    },
    {
        "id": 7,
        "name": "铺垫过长才给结论",
        "patterns": [],  # 用函数检测
        "reason": "第一秒抓不住注意力 = 失败",
        "fix": "第一句 headline，后面才是论证",
        "severity": "warn",
    },
    {
        "id": 8,
        "name": "学术腔开头",
        "patterns": [
            r"^综上所述",
            r"^值得注意的是",
            r"^从理论上来说",
            r"^根据分析",
            r"^首先.*其次.*最后",
            r"^综合来看",
            r"^总的来说",
        ],
        "reason": "表达 DNA 被破坏",
        "fix": "用'我跟你说''你听我说'开场",
        "severity": "warn",
    },
]

_HEDGING_WORDS = ["可能", "或许", "也许", "大概", "大约", "似乎", "也许可以", "也许能够"]
_HEDGING_PHRASES = ["这要看", "还需要看", "具体情况具体分析"]


def _count_hedging(text: str) -> int:
    """统计一句话中的 hedging 词数量。"""
    count = 0
    for w in _HEDGING_WORDS:
        count += text.count(w)
    for p in _HEDGING_PHRASES:
        count += text.count(p)
    return count


def _check_long_preamble(text: str) -> bool:
    """检测是否 4 段铺垫后才给结论。
    简单规则：前 4 段没有判断句式。
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) < 4:
        return False

    judgment_patterns = [
        r"我(建议|推荐|觉得|认为|跟你说|告诉你)",
        r"(应该|必须|不要|别|千万别|一定要)",
        r"(选|报|填|考)(这个|那个|什么|哪个)",
        r"你(这|那个).{0,5}(情况|分数|条件)",
    ]
    # 检查前 4 段是否有判断
    first_four = "\n\n".join(paragraphs[:4])
    for p in judgment_patterns:
        if re.search(p, first_four):
            return False
    return True


def check_anti_patterns(text: str, family_known: bool = False) -> list[AntiPatternMatch]:
    """检测文本中的决策反模式。

    Args:
        text: AI 生成的回复文本。
        family_known: 是否已知家庭背景（用于规则 2 的误报过滤）。

    Returns:
        命中的反模式列表（空列表 = 无问题）。
    """
    results: list[AntiPatternMatch] = []

    for rule in _RULES:
        if rule["id"] == 6:
            # 规则 6：一句话多次 hedging — 检查每个句子
            sentences = re.split(r"[。！？\n]", text)
            for sent in sentences:
                if len(sent.strip()) < 5:
                    continue
                if _count_hedging(sent) >= 2:
                    results.append(
                        AntiPatternMatch(
                            rule_id=6,
                            pattern=rule["name"],
                            reason=rule["reason"],
                            fix=rule["fix"],
                            matched_text=sent.strip()[:60],
                            severity=rule["severity"],
                        )
                    )
                    break  # 只报一次

        elif rule["id"] == 7:
            # 规则 7：铺垫过长
            if _check_long_preamble(text):
                results.append(
                    AntiPatternMatch(
                        rule_id=7,
                        pattern=rule["name"],
                        reason=rule["reason"],
                        fix=rule["fix"],
                        matched_text="前4段未见明确判断",
                        severity=rule["severity"],
                    )
                )

        elif rule["id"] == 2:
            # 规则 2：未问家庭即给热爱建议 — 如果已知家庭则跳过
            if family_known:
                continue
            for pat in rule["patterns"]:
                m = re.search(pat, text)
                if m:
                    results.append(
                        AntiPatternMatch(
                            rule_id=2,
                            pattern=rule["name"],
                            reason=rule["reason"],
                            fix=rule["fix"],
                            matched_text=m.group()[:60],
                            severity=rule["severity"],
                        )
                    )
                    break

        else:
            # 通用正则匹配
            for pat in rule["patterns"]:
                flags = re.IGNORECASE if rule["id"] == 8 else 0
                m = re.search(pat, text, flags=flags)
                if m:
                    results.append(
                        AntiPatternMatch(
                            rule_id=rule["id"],
                            pattern=rule["name"],
                            reason=rule["reason"],
                            fix=rule["fix"],
                            matched_text=m.group()[:60],
                            severity=rule["severity"],
                        )
                    )
                    break  # 每条规则只报一次

    return results


def get_error_count(matches: list[AntiPatternMatch]) -> int:
    """统计 error 级别的命中数。"""
    return sum(1 for m in matches if m.severity == "error")


def should_rewrite(matches: list[AntiPatternMatch], error_threshold: int = 1) -> bool:
    """判断是否需要重写（≥ error_threshold 个 error 即触发）。"""
    return get_error_count(matches) >= error_threshold


def format_report(matches: list[AntiPatternMatch]) -> str:
    """格式化检测报告（供调试/日志）。"""
    if not matches:
        return "✅ 无反模式命中"
    lines = [f"⚠️ 检测到 {len(matches)} 条反模式："]
    for m in matches:
        icon = "🔴" if m.severity == "error" else "🟡"
        lines.append(f"  {icon} [{m.rule_id}] {m.pattern}：{m.reason}")
        lines.append(f"     修复：{m.fix}")
        if m.matched_text:
            lines.append(f"     命中：{m.matched_text}")
    return "\n".join(lines)
