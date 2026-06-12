"""
测试数据年份标注 + 免责声明自动注入
覆盖：ensure_disclaimer、ensure_year_label
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import ensure_disclaimer, ensure_year_label, DATA_YEAR


DISCLAIMER_TEXT = "以上数据仅供参考"


class TestEnsureDisclaimer:
    """ensure_disclaimer: 回复末尾自动注入免责声明"""

    def test_disclaimer_added_when_missing(self):
        """无免责声明的回复 → 自动追加"""
        reply = "推荐清华大学，录取线 680 分。"
        result = ensure_disclaimer(reply)
        assert DISCLAIMER_TEXT in result
        assert result.startswith("推荐清华大学")
        # 免责声明在末尾
        assert result.endswith(DISCLAIMER_TEXT + "。")

    def test_disclaimer_not_duplicated(self):
        """已有免责声明 → 不重复添加"""
        reply = f"推荐清华大学。{DISCLAIMER_TEXT}，请以官方数据为准。"
        result = ensure_disclaimer(reply)
        assert result == reply

    def test_disclaimer_not_on_empty(self):
        """空回复 → 原样返回"""
        assert ensure_disclaimer("") == ""
        assert ensure_disclaimer(None) is None

    def test_disclaimer_not_on_error(self):
        """错误消息不加免责声明"""
        error_reply = "AI 服务出现异常，请稍后重试。"
        result = ensure_disclaimer(error_reply)
        assert result == error_reply

    def test_disclaimer_alread_present_partial_match(self):
        """回复包含免责关键字（不完全匹配标准措辞）→ 不追加"""
        reply = "以上数据仅供参考，具体请查询官网。"
        result = ensure_disclaimer(reply)
        assert result == reply


class TestEnsureYearLabel:
    """ensure_year_label: 推荐类回复自动注入数据年份标注"""

    def test_year_label_included_when_recommendation(self):
        """包含推荐关键词 → 自动标注数据年份"""
        reply = "冲一冲北京大学，稳一稳复旦大学。"
        result = ensure_year_label(reply)
        assert str(DATA_YEAR) in result

    def test_year_label_not_on_greeting(self):
        """问候语不含推荐关键词 → 不加年份"""
        reply = "你好！我是高考志愿顾问，有什么可以帮你的？"
        result = ensure_year_label(reply)
        assert result == reply

    def test_year_label_not_on_empty(self):
        """空回复 → 原样返回"""
        assert ensure_year_label("") == ""
        assert ensure_year_label(None) is None

    def test_year_label_not_duplicated(self):
        """已含年份标注 → 不重复"""
        reply = f"推荐 {DATA_YEAR} 年数据如下：冲北大稳复旦。"
        result = ensure_year_label(reply)
        assert result == reply

    def test_year_label_various_keywords(self):
        """多种推荐关键词均触发年份标注"""
        keywords = ["冲", "稳", "保", "志愿表", "录取线", "推荐"]
        for kw in keywords:
            reply = f"这是一段包含{kw}关键词的回复文本。"
            result = ensure_year_label(reply)
            assert str(DATA_YEAR) in result, f"关键词 '{kw}' 未触发年份标注"
