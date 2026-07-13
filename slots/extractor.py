"""
模块化槽位提取器 — 从用户消息中提取咨询所需的结构化信息。

将原来 agent.py 中 300+ 行的 extract_slots_from_message() 拆分为独立模块，
支持不可变模式（返回新副本而非修改原始状态）和情绪检测扩展。
"""

from __future__ import annotations

import copy
import re
from typing import Any

from config.constants import PROVINCES, SUBJECT_COMBOS_33, SUBJECT_SINGLE_33
from slots.patterns import (
    CHINESE_DIGIT_MAP,
    CHINESE_UNIT_MAP,
    DELTA_LINE_PATTERNS,
    DIALECT_PROVINCE_HINTS,
    FAMILY_KEYWORDS,
    GOAL_PATTERNS,
    INTEREST_KEYWORDS,
    INTEREST_NEGATIVE_PATTERN,
    INTEREST_POSITIVE_PATTERN,
    LINE_SCORE_PATTERNS,
    RANK_PATTERNS,
    REGION_KEYWORDS,
    SCORE_PATTERNS,
    SUBJECT_COMBOS_312,
    SUBJECT_PERM_VARIANTS,
)

# ── 选科组合正则 ──
_SUBJECT_COMBO_33_RE = re.compile(
    r"(物化生|物化政|物化地|物生政|物生地|物政地|"
    r"化生政|化生地|化政地|生政地|"
    r"物化史|物生史|物政史|物地史|"
    r"化生史|化政史|化地史|"
    r"生政史|生地史|政地史)"
)


def _create_default_slots() -> dict[str, dict[str, Any]]:
    """创建默认的空槽位字典。"""
    return {
        "province": {"label": "省份", "filled": False, "value": ""},
        "score_rank": {"label": "分数/位次", "filled": False, "value": ""},
        "subject": {"label": "选科", "filled": False, "value": ""},
        "interest": {"label": "专业兴趣/厌恶", "filled": False, "value": ""},
        "region": {"label": "地域偏好", "filled": False, "value": ""},
        "family": {"label": "家庭资源", "filled": False, "value": ""},
        "goal": {"label": "核心诉求", "filled": False, "value": ""},
    }


# ── 辅助函数 ──


def chinese_num_to_int(text: str) -> int | None:
    """将中文数字（如'五百八十'）转换为整数。支持到万位。"""
    if not text:
        return None
    result = 0
    current = 0
    wan_part = 0
    for ch in text:
        if ch in CHINESE_DIGIT_MAP:
            current = CHINESE_DIGIT_MAP[ch]
        elif ch in CHINESE_UNIT_MAP:
            u = CHINESE_UNIT_MAP[ch]
            if u == 10000:
                wan_part = (result + (current if current else 1)) * 10000
                result = 0
                current = 0
            else:
                if current == 0 and u == 10:
                    current = 1  # "十" 开头隐含 "一十"
                result += current * u
                current = 0
    result += current
    result += wan_part
    return result if result > 0 else None


def expand_subject_combo(abbr: str) -> str:
    """将 3+3 选科简称展开为完整表述，如 '物化生' → '物理+化学+生物'。"""
    _abbr_map = {"物": "物理", "化": "化学", "生": "生物", "政": "政治", "史": "历史", "地": "地理"}
    return "+".join(_abbr_map.get(ch, ch) for ch in abbr)


def parse_oral_score(msg: str) -> int | None:
    """解析口语化分数表达，如 '五百八'、'六百出头' → 整数分数。

    处理省略"十"的口语习惯：
      五百八 → 580（= 五百八十）
      六百一 → 610（= 六百一十）
      六百 → 600
    """
    # 匹配 "X百Y" 模式（Y 可选，省略"十"）
    m = re.search(r"([一二三四五六七八九两])百([一二三四五六七八九零])?(?:出头|左右)?", msg)
    if m:
        bai = CHINESE_DIGIT_MAP.get(m.group(1), 0) * 100
        shi = CHINESE_DIGIT_MAP.get(m.group(2), 0) * 10 if m.group(2) else 0
        val = bai + shi
        if 100 <= val <= 750:
            return val
    # 匹配 "X百" 纯百位
    m2 = re.search(r"([一二三四五六七八九两])百(?:出头|左右)?(?:\s|$|，|,|。)", msg)
    if m2:
        val = CHINESE_DIGIT_MAP.get(m2.group(1), 0) * 100
        if 100 <= val <= 750:
            return val
    return None


# ── 情绪检测 ──

_EMOTION_PATTERNS: list[tuple[str, str]] = [
    (r"急|着急|马上|来不及|快|赶紧|焦虑|慌", "急躁"),
    (r"迷茫|不知道|没方向|纠结|犹豫|不懂|不清楚|困惑", "迷茫"),
    (r"担心|害怕|怕|焦虑|紧张|不安|忧", "焦虑"),
    (r"自信|稳了|肯定|没问题|随便|一定|必上", "自信"),
    (r"崩溃|绝望|完了|没戏|算了|放弃|不读了", "崩溃"),
]


def detect_emotion(msg: str) -> str | None:
    """从用户消息中检测情绪状态。

    Returns:
        情绪标签（急躁/迷茫/焦虑/自信/崩溃）或 None
    """
    for pattern, emotion in _EMOTION_PATTERNS:
        if re.search(pattern, msg):
            return emotion
    return None


# ── 核心提取器 ──


class SlotExtractor:
    """模块化槽位提取器。

    支持两种使用模式：
    1. 就地修改（默认）：extract(msg, slots) 直接修改传入的 slots
    2. 不可变模式：extract(msg) 返回新的 slots 副本
    """

    def __init__(self):
        """初始化提取器，预编译所有正则表达式。"""
        self._province_re = re.compile(r"(" + "|".join(PROVINCES) + r")")
        self._province_context_re = re.compile(
            r"(?:在|到|去|来|我是|我家在|老家|籍贯|户籍)(?:的|了|位于|住在)?"
            r"\s*(" + "|".join(PROVINCES) + r")"
            r"|(" + "|".join(PROVINCES) + r")(?:考生|的|人|高考|参加高考|读高中|上的学)"
        )
        self._interest_negative_re = re.compile(INTEREST_NEGATIVE_PATTERN)
        self._interest_positive_re = re.compile(INTEREST_POSITIVE_PATTERN)

    def extract(self, msg: str, slots: dict | None = None) -> tuple[dict[str, dict[str, Any]], list[str]]:
        """从用户消息中提取槽位信息。

        Args:
            msg: 用户消息文本
            slots: 现有槽位字典。为 None 时创建新的默认槽位。

        Returns:
            (updated_slots, updated_fields) 元组：
            - updated_slots: 更新后的槽位字典
            - updated_fields: 被更新的字段名列表（如 ["省份→山东", "分数→580分"]）
        """
        s = slots if slots is not None else _create_default_slots()
        updated: list[str] = []

        self._extract_province(msg, s, updated)
        self._extract_score_rank(msg, s, updated)
        self._extract_subject(msg, s, updated)
        self._extract_region(msg, s, updated)
        self._extract_family(msg, s, updated)
        self._extract_goal(msg, s, updated)
        self._extract_interest(msg, s, updated)

        return s, updated

    def extract_new(self, msg: str, slots: dict | None = None) -> tuple[dict[str, dict[str, Any]], list[str]]:
        """不可变模式：返回新的槽位副本，不修改原始数据。"""
        base = slots if slots is not None else _create_default_slots()
        new_slots = copy.deepcopy(base)
        return self.extract(msg, new_slots)

    def _extract_province(self, msg: str, s: dict, updated: list[str]) -> None:
        """省份检测：支持精确匹配、上下文匹配、方言推测。"""
        if s["province"]["filled"]:
            return

        # 上下文匹配："我是河南人"、"在山东考的"
        m = self._province_context_re.search(msg)
        if m:
            prov = m.group(1) or m.group(2)
            if prov:
                s["province"]["value"] = prov
                s["province"]["filled"] = True
                updated.append(f"省份→{prov}")
                return

        # 直接匹配省份名
        for p in PROVINCES:
            if p in msg:
                s["province"]["value"] = p
                s["province"]["filled"] = True
                updated.append(f"省份→{p}")
                return

        # 方言→省份推测
        for dialect, candidates in DIALECT_PROVINCE_HINTS.items():
            if dialect in msg:
                s["province"]["value"] = candidates[0]
                s["province"]["filled"] = True
                updated.append(f"省份→{candidates[0]}(方言推测)")
                return

    def _extract_score_rank(self, msg: str, s: dict, updated: list[str]) -> None:
        """分数/位次检测：支持数字分数、中文数字、口语化表达、位次。"""
        if s["score_rank"]["filled"]:
            return

        # 1. 数字分数
        score_match = None
        for sp in SCORE_PATTERNS:
            m = re.search(sp, msg)
            if m:
                score_match = m
                break

        # 2. 中文数字分数
        cn_score_match = None
        if not score_match:
            cn_re = re.search(r"([一-鿿]{2,6})\s*分", msg)
            if cn_re:
                cn_num = chinese_num_to_int(cn_re.group(1))
                if cn_num and 100 <= cn_num <= 750:
                    cn_score_match = cn_num

        # 3. 口语化中文数字（不带"分"字）
        oral_score_match = None
        if not score_match and not cn_score_match:
            oral_score_match = parse_oral_score(msg)

        # 4. 分数差值表达
        delta_line_match = None
        if not score_match and not cn_score_match and not oral_score_match:
            for pat, fmt in DELTA_LINE_PATTERNS:
                m = re.search(pat, msg)
                if m:
                    delta_line_match = fmt.format(m.group(1))
                    break

        # 5. 一本线/特殊线上 N 分
        line_score_match = None
        if not score_match and not cn_score_match and not oral_score_match and not delta_line_match:
            for pat in LINE_SCORE_PATTERNS:
                line_re = re.search(pat, msg)
                if line_re:
                    line_score_match = f"一本线上{line_re.group(1)}分"
                    break

        # 6. 位次
        rank_value = None
        for rp in RANK_PATTERNS:
            m = re.search(rp, msg)
            if m:
                raw = m.group(1)
                if "万" in rp and "." in raw:
                    rank_value = str(int(float(raw) * 10000))
                elif "万" in rp:
                    rank_value = str(int(raw) * 10000)
                else:
                    rank_value = raw
                break

        # 应用检测结果
        if score_match:
            score_val = score_match.group(1)
            # Validate score is in reasonable range (0-750 for standard gaokao, up to 900 for Hainan)
            try:
                score_int = int(score_val)
                if score_int < 0 or score_int > 900:
                    score_val = ""
            except (ValueError, TypeError):
                score_val = ""
            if score_val:
                s["score_rank"]["value"] = score_val + "分"
                s["score_rank"]["filled"] = True
                updated.append(f"分数→{score_val}分")
        elif cn_score_match:
            try:
                cn_val = int(cn_score_match)
                if cn_val < 0 or cn_val > 900:
                    cn_score_match = None
            except (ValueError, TypeError):
                cn_score_match = None
            if cn_score_match is not None:
                s["score_rank"]["value"] = str(cn_score_match) + "分"
                s["score_rank"]["filled"] = True
                updated.append(f"分数→{cn_score_match}分")
        elif oral_score_match:
            try:
                oral_val = int(oral_score_match)
                if oral_val < 0 or oral_val > 900:
                    oral_score_match = None
            except (ValueError, TypeError):
                oral_score_match = None
            if oral_score_match is not None:
                s["score_rank"]["value"] = str(oral_score_match) + "分"
                s["score_rank"]["filled"] = True
                updated.append(f"分数→{oral_score_match}分")
        elif delta_line_match:
            s["score_rank"]["value"] = delta_line_match
            s["score_rank"]["filled"] = True
            updated.append(f"分数→{delta_line_match}")
        elif line_score_match:
            s["score_rank"]["value"] = line_score_match
            s["score_rank"]["filled"] = True
            updated.append(f"分数→{line_score_match}")

        if rank_value and not s["score_rank"]["filled"]:
            s["score_rank"]["value"] = "位次" + rank_value
            s["score_rank"]["filled"] = True
            updated.append(f"位次→{rank_value}")
        elif rank_value and s["score_rank"]["filled"] and "位次" not in s["score_rank"]["value"]:
            s["score_rank"]["value"] += " / 位次" + rank_value
            updated.append(f"位次→{rank_value}")

    def _extract_subject(self, msg: str, s: dict, updated: list[str]) -> None:
        """选科检测：支持 3+1+2 / 3+3 全组合 + 自然表达。"""
        if s["subject"]["filled"]:
            return

        # 构建完整组合列表
        subject_combos = list(SUBJECT_COMBOS_312)
        existing = set(subject_combos)

        for combo in SUBJECT_COMBOS_33:
            if combo not in existing:
                subject_combos.append(combo)

        for v in SUBJECT_PERM_VARIANTS:
            if v not in existing:
                subject_combos.append(v)
                existing.add(v)

        # 匹配组合
        matched_subj = None
        for subj in subject_combos:
            if subj in msg:
                matched_subj = subj
                break

        # 3+3 自然表达："选了物理化学地理"
        if not matched_subj:
            all_subject_names = "|".join(SUBJECT_SINGLE_33)
            natural_33_re = re.search(
                r"(?:选[的了考]?|选考)\s*(" + all_subject_names + r")\s*"
                r"(" + all_subject_names + r")?\s*"
                r"(" + all_subject_names + r")?",
                msg,
            )
            if natural_33_re:
                parts = [natural_33_re.group(i) for i in (1, 2, 3) if natural_33_re.group(i)]
                if len(parts) >= 2:
                    matched_subj = "+".join(parts)

        # 单科自然表达："选的物理"
        if not matched_subj:
            single_33 = "|".join(SUBJECT_SINGLE_33)
            subj_natural_re = re.search(r"(?:选[的了]?|学[的了]?|考[的了]?|方向)\s*(" + single_33 + r")", msg)
            if subj_natural_re:
                matched_subj = subj_natural_re.group(1)

        # 裸关键词
        if not matched_subj:
            for subj in SUBJECT_SINGLE_33:
                if subj in msg:
                    matched_subj = subj
                    break

        if matched_subj:
            s["subject"]["value"] = matched_subj
            s["subject"]["filled"] = True
            updated.append(f"选科→{matched_subj}")

    def _extract_region(self, msg: str, s: dict, updated: list[str]) -> None:
        """地域偏好检测。"""
        if s["region"]["filled"]:
            return
        for r in REGION_KEYWORDS:
            if r in msg:
                s["region"]["value"] = r
                s["region"]["filled"] = True
                updated.append(f"地域→{r}")
                return

    def _extract_family(self, msg: str, s: dict, updated: list[str]) -> None:
        """家庭资源检测。"""
        if s["family"]["filled"]:
            return
        for fw in FAMILY_KEYWORDS:
            if fw in msg:
                s["family"]["value"] = fw
                s["family"]["filled"] = True
                updated.append(f"家庭→{fw}")
                return

    def _extract_goal(self, msg: str, s: dict, updated: list[str]) -> None:
        """核心诉求检测。"""
        if s["goal"]["filled"]:
            return
        for pattern, goal_val in GOAL_PATTERNS:
            m = re.search(pattern, msg)
            if m:
                s["goal"]["value"] = goal_val if goal_val else m.group(1)
                s["goal"]["filled"] = True
                updated.append(f"诉求→{s['goal']['value']}")
                return

    def _extract_interest(self, msg: str, s: dict, updated: list[str]) -> None:
        """兴趣/厌恶检测：支持正面/负面表达 + 关键词兜底。"""
        if s["interest"]["filled"]:
            return

        # 负面兴趣优先检查（"不想学"包含"想学"子串）
        neg_match = self._interest_negative_re.search(msg)
        if neg_match:
            val = neg_match.group(1)
            s["interest"]["value"] = f"不想学{val}"
            s["interest"]["filled"] = True
            updated.append(f"兴趣→不想学{val}")
            return

        # 正面兴趣
        pos_match = self._interest_positive_re.search(msg)
        if pos_match:
            val = pos_match.group(1)
            s["interest"]["value"] = f"想学{val}"
            s["interest"]["filled"] = True
            updated.append(f"兴趣→想学{val}")
            return

        # 关键词兜底
        matched_interests = [kw for kw in INTEREST_KEYWORDS if kw in msg]
        if matched_interests:
            s["interest"]["value"] = " ".join(matched_interests[:3])
            s["interest"]["filled"] = True
            updated.append(f"兴趣→{'、'.join(matched_interests[:3])}")


# ── 便捷函数（保持与原 agent.py 兼容） ──

_default_extractor = SlotExtractor()

# 默认槽位模板（供外部引用）
DEFAULT_SLOTS = _create_default_slots()


def filled_slots(slots: dict | None = None) -> dict:
    """返回已填充的槽位。"""
    s = slots if slots is not None else DEFAULT_SLOTS
    return {k: v for k, v in s.items() if v["filled"]}


def missing_slots(slots: dict | None = None) -> list[str]:
    """返回未填充的槽位 key 列表。"""
    s = slots if slots is not None else DEFAULT_SLOTS
    return [k for k, v in s.items() if not v["filled"]]


def slots_summary(slots: dict | None = None) -> str:
    """返回槽位状态的文本摘要。"""
    s = slots if slots is not None else DEFAULT_SLOTS
    lines = []
    for _k, v in s.items():
        status = "[OK]" if v["filled"] else "[ ]"
        lines.append(f"  {status} {v['label']}: {v['value'] if v['filled'] else '(未填)'}")
    return "\n".join(lines)


def extract_slots_from_message(msg: str, slots: dict | None = None) -> list[str]:
    """从用户消息中自动提取槽位信息（兼容原 agent.py 接口）。

    Returns:
        被更新的字段描述列表（如 ["省份→山东", "分数→580分"]）
    """
    _s, updated = _default_extractor.extract(msg, slots)
    return updated
