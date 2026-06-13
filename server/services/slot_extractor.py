"""Slot extraction from user messages — extracted from agent.py."""
import re
from typing import Optional

from constants import PROVINCES

CHINESE_NUM_MAP = {
    "零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "百": 100, "千": 1000, "万": 10000,
}

DIALECT_MAP = {"俺": "山东", "俺们": "山东", "咱": "河北"}

SUBJECT_3PLUS3_PATTERNS = {
    "物理+化学+生物": ["物理", "化学", "生物"],
    "物理+化学+地理": ["物理", "化学", "地理"],
    "物理+化学+政治": ["物理", "化学", "政治"],
    "物理+生物+地理": ["物理", "生物", "地理"],
    "物理+生物+政治": ["物理", "生物", "政治"],
    "物理+地理+政治": ["物理", "地理", "政治"],
    "历史+化学+生物": ["历史", "化学", "生物"],
    "历史+化学+地理": ["历史", "化学", "地理"],
    "历史+化学+政治": ["历史", "化学", "政治"],
    "历史+生物+地理": ["历史", "生物", "地理"],
    "历史+生物+政治": ["历史", "生物", "政治"],
    "历史+地理+政治": ["历史", "地理", "政治"],
}

SLOT_KEYS = ["province", "score", "subject", "interest", "region", "family", "goal"]


def _chinese_to_number(text: str) -> Optional[int]:
    """Convert Chinese numeral text (e.g. '五百八十') to integer. Supports up to 万.

    Handles the standard positional notation:
      六百二十 -> 620, 六百 -> 600, 五百八十 -> 580, 三千 -> 3000
    """
    if not text:
        return None
    digit_map = {
        "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
        "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
    }
    unit_map = {"十": 10, "百": 100, "千": 1000, "万": 10000}
    result = 0
    current = 0
    wan_part = 0
    for ch in text:
        if ch in digit_map:
            current = digit_map[ch]
        elif ch in unit_map:
            u = unit_map[ch]
            if u == 10000:
                wan_part = (result + (current if current else 1)) * 10000
                result = 0
                current = 0
            else:
                if current == 0 and u == 10:
                    current = 1  # "十" at start implies "一十"
                result += current * u
                current = 0
    result += current
    result += wan_part
    return result if result > 0 else None


class SlotExtractor:
    """Extract structured slots from natural language user messages.

    Parses gaokao-related user input and returns a dict with keys:
    province, score, subject, interest, region, family, goal.
    Each value is either a parsed string/int or None.
    """

    def extract(self, text: str) -> dict:
        """Extract all slots from a user message."""
        if not text or not text.strip():
            return {k: None for k in SLOT_KEYS}
        return {
            "province": self._extract_province(text),
            "score": self._extract_score(text),
            "subject": self._extract_subject(text),
            "interest": self._extract_interest(text),
            "region": None,
            "family": self._extract_family(text),
            "goal": self._extract_goal(text),
        }

    def _extract_province(self, text: str) -> Optional[str]:
        """Extract province name from text.

        Checks the canonical PROVINCES list first, then falls back to
        dialect-based heuristics (e.g. 俺 -> 山东).
        """
        for p in PROVINCES:
            if p in text:
                return p
        for dialect, province in DIALECT_MAP.items():
            if dialect in text:
                return province
        return None

    def _extract_score(self, text: str) -> Optional[int]:
        """Extract numeric score from text.

        Handles:
        - Digit scores: "620分", "考了630分"
        - Chinese numeral scores: "六百二十分"
        """
        m = re.search(r"(\d{2,4})\s*分", text)
        if m:
            return int(m.group(1))
        # Build a character class from the Chinese number map digits/units
        _cn_chars = "".join(CHINESE_NUM_MAP.keys())
        _cn_pattern = rf"([{_cn_chars}]+)分"
        m = re.search(_cn_pattern, text)
        if m:
            num = _chinese_to_number(m.group(1))
            if num and 100 <= num <= 750:
                return num
        return None

    def _extract_subject(self, text: str) -> Optional[str]:
        """Extract subject selection from text.

        Recognizes:
        - 3+3 subject combinations (e.g. 物理+化学+生物)
        - Legacy science/liberal arts (理科/文科)
        - Individual subjects (物理/历史)
        """
        for combo, keywords in SUBJECT_3PLUS3_PATTERNS.items():
            if all(k in text for k in keywords):
                return combo
        if "理科" in text:
            return "理科"
        if "文科" in text:
            return "文科"
        if "物理" in text:
            return "物理"
        if "历史" in text:
            return "历史"
        return None

    def _extract_interest(self, text: str) -> Optional[str]:
        """Extract major/field interest from text.

        Looks for patterns like "想学X", "喜欢X", "感兴趣" followed by
        a major name, or falls back to keyword matching against common majors.
        """
        m = re.search(r"(?:想学|喜欢|感兴趣|意向)[的方向是]*\s*(.+?)(?:[，。,.\s]|$)", text)
        if m:
            return m.group(1).strip()
        majors = ["计算机", "金融", "医学", "法学", "教育", "工程", "艺术", "文学", "管理"]
        for major in majors:
            if major in text:
                return major
        return None

    def _extract_goal(self, text: str) -> Optional[str]:
        """Extract future goal/aspiration from text.

        Maps various Chinese expressions to normalized goal values:
        考研, 出国, 就业, 考公.
        """
        goals = {
            "考研": "考研", "读研": "考研",
            "出国": "出国", "留学": "出国",
            "工作": "就业", "就业": "就业",
            "考公": "考公", "考编": "考公",
        }
        for keyword, value in goals.items():
            if keyword in text:
                return value
        return None

    def _extract_family(self, text: str) -> Optional[str]:
        """Extract family background/resource information from text.

        Maps expressions like 农村, 城市, 体制内, 经商 to normalized values.
        """
        keywords = {
            "农村": "农村", "城市": "城市", "小镇": "小城镇",
            "体制内": "体制内", "公务员": "体制内",
            "经商": "经商", "做生意": "经商",
        }
        for kw, val in keywords.items():
            if kw in text:
                return val
        return None
