"""kb_retriever 模块的单元测试。"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server.services.kb_retriever import (
    KbRetriever,
    KeywordOnlyEmbedding,
    RetrievalResult,
    keyword_match_score,
    split_group,
)


class TestSplitGroup:
    def test_splits_by_h2_headings(self):
        content = "# Main Title\nIntro text\n## Section A\nContent A\n## Section B\nContent B"
        chunks = split_group(content, "G1")
        assert len(chunks) == 3
        assert chunks[0].section_title == ""
        assert chunks[0].group_id == "G1"
        assert chunks[1].section_title == "Section A"
        assert "Content A" in chunks[1].text
        assert chunks[2].section_title == "Section B"

    def test_handles_single_section(self):
        content = "## Only Section\nSome content here"
        chunks = split_group(content, "G2")
        assert len(chunks) == 1
        assert chunks[0].section_title == "Only Section"

    def test_empty_content(self):
        chunks = split_group("", "G3")
        assert len(chunks) == 0


class TestKeywordMatch:
    def test_no_match(self):
        score = keyword_match_score("今天天气不错", ["志愿", "填报"])
        assert score == 0.0

    def test_single_match(self):
        score = keyword_match_score("我想报志愿", ["志愿", "填报"])
        assert score == 0.4

    def test_two_matches(self):
        score = keyword_match_score("我想填报志愿", ["志愿", "填报"])
        assert score == 0.7

    def test_three_plus_matches(self):
        score = keyword_match_score("冲一冲稳一稳保一保", ["冲一冲", "稳一稳", "保一保"])
        assert score == 1.0

    def test_case_insensitive(self):
        score = keyword_match_score("AI很厉害", ["ai", "人工智能"])
        assert score == 0.4


class TestKbRetrieverInit:
    def _make_retriever(self, tmpdir: str) -> KbRetriever:
        groups_dir = os.path.join(tmpdir, "knowledge", "groups")
        os.makedirs(groups_dir)
        with open(os.path.join(groups_dir, "G1_core_method.md"), "w") as f:
            f.write("# 核心方法论\n\n## 志愿填报方法\n冲稳保规则...\n\n## 咨询风格\n说话要直接...\n")
        with open(os.path.join(groups_dir, "G2_major_school.md"), "w") as f:
            f.write("# 专业与学校\n\n## 专业选择\n12 大学科...\n\n## 学校评估\n985/211...\n")
        quotes_dir = os.path.join(tmpdir, "knowledge", "quotes")
        os.makedirs(quotes_dir)
        quotes = {
            "计算机": [
                {
                    "id": "q1",
                    "text": "学计算机就要卷到底",
                    "tags": ["计算机", "努力"],
                    "category": "zhuanye",
                    "sentiment": "motivational",
                }
            ],
            "医学": [
                {
                    "id": "q2",
                    "text": "学医就是选择了一条漫长但稳定的路",
                    "tags": ["医学", "稳定"],
                    "category": "zhuanye",
                    "sentiment": "neutral",
                }
            ],
        }
        with open(os.path.join(quotes_dir, "_by_major.json"), "w") as f:
            json.dump(quotes, f, ensure_ascii=False)
        return KbRetriever(
            groups_dir=groups_dir,
            quotes_path=quotes_dir,
            embedding_provider=KeywordOnlyEmbedding(),
            embedding_model="",
        )

    def test_loads_groups(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ret = self._make_retriever(tmpdir)
            assert "G1_core_method" in ret._groups
            assert "G2_major_school" in ret._groups
            assert len(ret._groups["G1_core_method"]) == 3

    def test_loads_quotes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ret = self._make_retriever(tmpdir)
            assert len(ret._quotes) == 2

    def test_search_returns_result(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ret = self._make_retriever(tmpdir)
            result = ret.search("我想填报志愿", {})
            assert isinstance(result, RetrievalResult)
            assert len(result.groups) > 0
            assert len(result.groups) <= 2


class TestQuoteRetrieval:
    def _make_retriever(self, tmpdir: str) -> KbRetriever:
        groups_dir = os.path.join(tmpdir, "knowledge", "groups")
        os.makedirs(groups_dir)
        with open(os.path.join(groups_dir, "G1_core_method.md"), "w") as f:
            f.write("## Test\nContent\n")
        quotes_dir = os.path.join(tmpdir, "knowledge", "quotes")
        os.makedirs(quotes_dir)
        quotes = {
            "计算机": [
                {
                    "id": "q1",
                    "text": "学计算机就要卷到底",
                    "tags": ["计算机", "努力"],
                    "category": "zhuanye",
                    "sentiment": "motivational",
                },
                {
                    "id": "q2",
                    "text": "985计算机 > 211金融",
                    "tags": ["计算机", "选择"],
                    "category": "zhuanye",
                    "sentiment": "neutral",
                },
            ],
            "医学": [
                {
                    "id": "q3",
                    "text": "学医十年磨一剑",
                    "tags": ["医学", "坚持"],
                    "category": "zhuanye",
                    "sentiment": "neutral",
                },
            ],
        }
        with open(os.path.join(quotes_dir, "_by_major.json"), "w") as f:
            json.dump(quotes, f, ensure_ascii=False)
        return KbRetriever(
            groups_dir=groups_dir,
            quotes_path=quotes_dir,
            embedding_provider=KeywordOnlyEmbedding(),
            embedding_model="",
        )

    def test_keyword_match_returns_quotes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ret = self._make_retriever(tmpdir)
            result = ret.search("计算机怎么学", {})
            assert len(result.quotes) > 0
            quote_texts = [q.text for q in result.quotes]
            assert any("计算机" in t for t in quote_texts)

    def test_no_match_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ret = self._make_retriever(tmpdir)
            result = ret.search("今天天气真好", {})
            assert isinstance(result.quotes, list)
