"""G9 张雪峰方法论溯源知识组测试。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kb_retriever import KbRetriever, KeywordOnlyEmbedding, GROUP_TRIGGERS


_QUOTES_DIR = os.path.join(os.path.dirname(__file__), "..", "knowledge", "quotes")
_GROUPS_DIR = os.path.join(os.path.dirname(__file__), "..", "knowledge", "groups")
_G9_PATH = os.path.join(_GROUPS_DIR, "G9_zhangxuefeng_methodology_origin.md")


def _make_retriever() -> KbRetriever:
    return KbRetriever(
        groups_dir=_GROUPS_DIR,
        quotes_path=_QUOTES_DIR,
        embedding_provider=KeywordOnlyEmbedding(),
    )


class TestG9FileExists:
    """G9 知识组文件存在性测试。"""

    def test_g9_file_exists(self) -> None:
        assert os.path.exists(_G9_PATH), f"G9 file missing: {_G9_PATH}"

    def test_g9_file_has_content(self) -> None:
        with open(_G9_PATH, encoding="utf-8") as f:
            content = f.read()
        assert len(content) > 200, "G9 should have substantial content"

    def test_g9_has_required_sections(self) -> None:
        with open(_G9_PATH, encoding="utf-8") as f:
            content = f.read()
        for section in ["9.1", "9.2", "9.3", "9.4", "9.5", "9.6", "9.7"]:
            assert section in content, f"Missing section {section} in G9"


class TestG9Triggers:
    """G9 触发词测试。"""

    def test_g9_in_trigger_registry(self) -> None:
        assert "G9_zhangxuefeng_methodology_origin" in GROUP_TRIGGERS

    def test_g9_triggers_cover_zhangxuefeng(self) -> None:
        triggers = GROUP_TRIGGERS["G9_zhangxuefeng_methodology_origin"]
        assert "张雪峰" in triggers, "应包含'张雪峰'"
        assert "雪峰" in triggers, "应包含'雪峰'"

    def test_g9_triggers_cover_methodology_origin(self) -> None:
        triggers = GROUP_TRIGGERS["G9_zhangxuefeng_methodology_origin"]
        assert "为什么这么说" in triggers, "应包含溯源类"
        assert "批评" in triggers, "应包含批评/盲点"
        assert "盲点" in triggers, "应包含'盲点'"

    def test_g9_triggers_cover_life_events(self) -> None:
        triggers = GROUP_TRIGGERS["G9_zhangxuefeng_methodology_origin"]
        assert "他的人生" in triggers or "张雪峰的经历" in triggers, \
            "应包含人物经历类触发词"


class TestG9Retrieval:
    """G9 召回测试。"""

    def test_zhangxuefeng_explicit_recall(self) -> None:
        """'张雪峰'应召回 G9。"""
        r = _make_retriever()
        result = r.search("张雪峰是怎么走到今天的？", {})
        assert "G9_zhangxuefeng_methodology_origin" in result.groups, \
            f"Expected G9 in {result.groups}"

    def test_zhangxuefeng_methodology_question(self) -> None:
        """'张雪峰的方法论'应召回 G9。"""
        r = _make_retriever()
        result = r.search("张雪峰的方法论是什么？", {})
        assert "G9_zhangxuefeng_methodology_origin" in result.groups

    def test_criticism_blind_spot_question(self) -> None:
        """'张雪峰的盲点'应召回 G9。"""
        r = _make_retriever()
        result = r.search("张雪峰的方法有什么盲点？", {})
        assert "G9_zhangxuefeng_methodology_origin" in result.groups

    def test_decision_timeline_question(self) -> None:
        """'张雪峰的人生决策'应召回 G9。"""
        r = _make_retriever()
        result = r.search("张雪峰的人生经历了哪些关键决策？", {})
        assert "G9_zhangxuefeng_methodology_origin" in result.groups

    def test_normal_volunteer_query_no_g9(self) -> None:
        """普通志愿问题不应召回 G9。"""
        r = _make_retriever()
        queries = [
            "我580分湖北，想学计算机",
            "山东600分位次怎么算",
            "数学专业好不好就业",
        ]
        for query in queries:
            result = r.search(query, {})
            assert "G9_zhangxuefeng_methodology_origin" not in result.groups, \
                f"Unexpected G9 in normal query: {query}"


class TestG9ContentQuality:
    """G9 内容质量测试（保证 LLM 拿到的是高质量内容）。"""

    def test_g9_chunk_about_zhangxuefeng(self) -> None:
        """被召回的 G9 chunks 应是关于张雪峰的内容（含'张雪峰'或雪峰关联词）。"""
        r = _make_retriever()
        result = r.search("张雪峰", {})
        zx_chunks = [c for c in result.group_chunks if c.group_id == "G9_zhangxuefeng_methodology_origin"]
        if zx_chunks:
            for c in zx_chunks:
                # 该段可能在切分时没有"张雪峰"字样，但仍应是关于他的内容
                # （行为模式/盲点/决策/方法论都是关于张雪峰）
                related_signals = [
                    "张雪峰", "雪峰", "他的", "张子彪", "峰学蔚来",
                    "考研辅导", "新闻学", "生化环材", "齐齐哈尔", "郑州大学",
                    "苏州", "争议", "流量", "IP", "教育", "言论", "直播",
                    "演说家", "阶层", "就业", "选择", "努力",
                ]
                assert any(sig in c.text for sig in related_signals), \
                    f"G9 chunk should be about 张雪峰: {c.section_title}"


class TestG9NoRegression:
    """回归测试：增加 G9 后其他 8 个 group 仍正常工作。"""

    def test_all_8_existing_groups_still_loadable(self) -> None:
        """G1-G8 应仍能被加载。"""
        r = _make_retriever()
        expected = {
            "G1_core_method", "G2_major_school", "G3_career_future",
            "G4_life_planning", "G5_data_format", "G6_quick_ref",
            "G7_employment_paths", "G8_graduate_and_vocational",
        }
        assert expected.issubset(set(r._groups.keys())), \
            f"Missing: {expected - set(r._groups.keys())}"

    def test_g9_does_not_break_normal_rag(self) -> None:
        """普通 RAG 检索流程不应被 G9 干扰。"""
        r = _make_retriever()
        result = r.search("985 大学有哪些", {})
        # 应至少召回 G2（专业/学校）
        assert "G2_major_school" in result.groups, \
            f"Normal RAG broken: {result.groups}"
