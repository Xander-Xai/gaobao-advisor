"""test_hallucination — 幻觉检测器测试。"""

from __future__ import annotations

import pytest

from quality.judge.hallucination import HallucinationDetector


class TestHallucinationDetector:
    """HallucinationDetector 测试。"""

    def setup_method(self) -> None:
        self.detector = HallucinationDetector()

    # ── 干净回答（无幻觉标记） ──────────────────────────────────────

    def test_clean_reply_no_flags(self) -> None:
        """干净回答不应产生任何标记。"""
        reply = "你可以根据自己的兴趣和分数来选择专业。"
        knowledge = "兴趣和分数是选择专业的重要因素。"
        flags = self.detector.detect(reply, knowledge_chunks=knowledge)
        assert flags == []

    def test_clean_reply_with_matching_numbers(self) -> None:
        """数字在知识库中存在，不应标记。"""
        reply = "清华大学录取分数线大约680分。"
        knowledge = "清华大学2024年录取分数线680分。"
        flags = self.detector.detect(reply, knowledge_chunks=knowledge)
        # 680 在知识库中，不应标记为 numeric 幻觉
        numeric_flags = [f for f in flags if f.startswith("numeric:")]
        assert numeric_flags == []

    def test_clean_reply_with_matching_school(self) -> None:
        """学校名称在知识库中存在，不应标记。"""
        reply = "推荐考虑浙江大学。"
        knowledge = "浙江大学是一所综合性大学。"
        flags = self.detector.detect(reply, knowledge_chunks=knowledge)
        school_flags = [f for f in flags if f.startswith("entity_school:")]
        assert school_flags == []

    # ── 数字幻觉检测 ────────────────────────────────────────────────

    def test_numeric_hallucination_detected(self) -> None:
        """数字不在知识库中，应标记。"""
        reply = "这个专业录取分数线是680分。"
        knowledge = "该专业录取分数线为620分。"
        flags = self.detector.detect(reply, knowledge_chunks=knowledge)
        numeric_flags = [f for f in flags if f.startswith("numeric:")]
        assert len(numeric_flags) >= 1
        # 680 不在知识库中
        assert any("680" in f for f in numeric_flags)

    def test_numeric_hallucination_no_knowledge(self) -> None:
        """无知识库时不进行数字验证（无法验证，不标记）。"""
        reply = "录取分数线680分。"
        flags = self.detector.detect(reply, knowledge_chunks=None)
        # 无知识库时，knowledge_text 为空字符串，条件 `if knowledge_text` 为 False
        # 无法验证数字真伪，不应标记
        numeric_flags = [f for f in flags if f.startswith("numeric:")]
        assert numeric_flags == []

    def test_year_not_flagged(self) -> None:
        """年份不应被标记为数字幻觉。"""
        reply = "2024年高考政策有变化。"
        knowledge = "高考政策每年可能调整。"
        flags = self.detector.detect(reply, knowledge_chunks=knowledge)
        numeric_flags = [f for f in flags if f.startswith("numeric:")]
        assert numeric_flags == []

    def test_percentage_hallucination(self) -> None:
        """百分比数字不在知识库中，应标记。"""
        reply = "就业率达到95%。"
        knowledge = "就业率约为85%。"
        flags = self.detector.detect(reply, knowledge_chunks=knowledge)
        numeric_flags = [f for f in flags if f.startswith("numeric:")]
        assert any("95" in f for f in numeric_flags)

    # ── 实体幻觉检测 ────────────────────────────────────────────────

    def test_school_hallucination_detected(self) -> None:
        """学校名称不在知识库中，应标记。"""
        reply = "你可以考虑某某大学。"
        knowledge = "推荐院校：清华大学、北京大学。"
        flags = self.detector.detect(reply, knowledge_chunks=knowledge)
        school_flags = [f for f in flags if f.startswith("entity_school:")]
        assert any("某某大学" in f for f in school_flags)

    def test_common_school_whitelist(self) -> None:
        """常见知名学校（白名单）不应被标记。"""
        reply = "清华大学和北京大学都是顶尖学府。"
        knowledge = "顶尖学府有很多。"
        flags = self.detector.detect(reply, knowledge_chunks=knowledge)
        school_flags = [f for f in flags if f.startswith("entity_school:")]
        assert school_flags == []

    def test_major_hallucination_detected(self) -> None:
        """专业名称不在知识库中，应标记。"""
        reply = "量子计算工程是一个新兴专业。"
        knowledge = "热门专业包括计算机科学与技术、人工智能。"
        flags = self.detector.detect(reply, knowledge_chunks=knowledge)
        major_flags = [f for f in flags if f.startswith("entity_major:")]
        assert any("量子计算工程" in f for f in major_flags)

    # ── 来源引用缺失检测 ────────────────────────────────────────────

    def test_source_attribution_missing(self) -> None:
        """使用"数据显示"但未给出具体来源，应标记。"""
        reply = "数据显示，计算机专业就业率最高。"
        flags = self.detector.detect(reply)
        assert "source_missing" in flags

    def test_source_attribution_present(self) -> None:
        """使用"数据显示"并给出具体来源，不应标记。"""
        reply = "数据显示，计算机专业就业率最高。来源：教育部2024年公告"
        flags = self.detector.detect(reply)
        assert "source_missing" not in flags

    def test_source_attribution_with_book_reference(self) -> None:
        """引用具体书刊不应标记。"""
        reply = "据统计，根据《中国教育发展报告》，理工科占比最高。"
        flags = self.detector.detect(reply)
        assert "source_missing" not in flags

    def test_no_source_claim_no_flag(self) -> None:
        """没有使用"数据显示"等表述，不应标记。"""
        reply = "计算机专业就业前景不错。"
        flags = self.detector.detect(reply)
        assert "source_missing" not in flags

    # ── 边界情况 ────────────────────────────────────────────────────

    def test_empty_reply(self) -> None:
        """空回答不应产生任何标记。"""
        flags = self.detector.detect("")
        assert flags == []

    def test_whitespace_only_reply(self) -> None:
        """仅空白字符的回答不应产生标记。"""
        flags = self.detector.detect("   \n\t  ")
        assert flags == []

    def test_multiple_numeric_hallucinations(self) -> None:
        """多个数字幻觉应全部标记。"""
        reply = "录取线680分，学费5000元，就业率95%。"
        knowledge = "录取线620分。"
        flags = self.detector.detect(reply, knowledge_chunks=knowledge)
        numeric_flags = [f for f in flags if f.startswith("numeric:")]
        # 680, 5000, 95 都不在知识库中
        assert len(numeric_flags) >= 2  # 至少 680 和 95

    def test_source_missing_only_flagged_once(self) -> None:
        """来源缺失只标记一次。"""
        reply = "数据显示计算机好，据统计金融也好，研究表明医学也不错。"
        flags = self.detector.detect(reply)
        source_count = flags.count("source_missing")
        assert source_count <= 1
