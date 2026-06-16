"""张雪峰原版金句溯源测试。"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server.services.kb_retriever import _ZX_TRIGGERS, KbRetriever, KeywordOnlyEmbedding

_QUOTES_DIR = os.path.join(os.path.dirname(__file__), "..", "knowledge", "quotes")
_GROUPS_DIR = os.path.join(os.path.dirname(__file__), "..", "knowledge", "groups")


def _make_retriever() -> KbRetriever:
    """Create a keyword-only retriever for unit tests."""
    return KbRetriever(
        groups_dir=_GROUPS_DIR,
        quotes_path=_QUOTES_DIR,
        embedding_provider=KeywordOnlyEmbedding(),
    )


class TestZxQuoteLoading:
    """验证 zhangxuefeng_originals.json 被正确加载。"""

    def test_zx_quotes_are_loaded(self) -> None:
        """确认张雪峰原版金句被加载到语录列表。"""
        r = _make_retriever()
        zx_ids = {q.id for q in r._quotes if q.id.startswith("zx_")}
        assert len(zx_ids) >= 50, f"Expected ≥50 ZX quotes, got {len(zx_ids)}"

    def test_zx_quote_has_required_fields(self) -> None:
        """每条 ZX 金句必须包含 id/text/major/tags。"""
        r = _make_retriever()
        for q in r._quotes:
            if not q.id.startswith("zx_"):
                continue
            assert q.text, f"Missing text: {q.id}"
            assert q.major == "zhangxuefeng", f"Wrong major: {q.id}"
            assert q.tags, f"Missing tags: {q.id}"

    def test_zx_quote_with_year_has_source(self) -> None:
        """有具体年份的 ZX 金句必须有 source 字段。"""
        r = _make_retriever()
        for q in r._quotes:
            if q.id.startswith("zx_") and q.year > 0:
                assert q.source, f"Missing source for {q.id} (year={q.year})"

    def test_zx_quote_source_is_string(self) -> None:
        """source 字段必须是字符串。"""
        r = _make_retriever()
        for q in r._quotes:
            if q.id.startswith("zx_"):
                assert isinstance(q.source, str), f"source not str: {q.id}"

    def test_zx_quotes_dont_overwrite_existing(self) -> None:
        """ZX 金句不应覆盖已有金句（ID 以 zx_ 为前缀）。"""
        r = _make_retriever()
        existing_ids = {q.id for q in r._quotes if not q.id.startswith("zx_")}
        zx_ids = {q.id for q in r._quotes if q.id.startswith("zx_")}
        assert existing_ids.isdisjoint(zx_ids), "ZX IDs clash with existing quotes"


class TestZxQuoteSearch:
    """验证 ZX 金句在触发词下被优先召回。"""

    def test_explicit_zhangxuefeng_triggers_zx_quotes(self) -> None:
        """用户明确提及'张雪峰'时，ZX 金句应出现在前3。"""
        r = _make_retriever()
        result = r.search("张雪峰说新闻学不能报，是真的吗？", {})
        zx_ids = [q.id for q in result.quotes if q.id.startswith("zx_")]
        assert len(zx_ids) >= 1, f"Expected ZX quotes in results, got: {[x.id for x in result.quotes]}"
        # ZX 金句应出现在前 2 位(用户明确问张雪峰)
        assert result.quotes[0].id.startswith("zx_") or result.quotes[1].id.startswith("zx_"), (
            f"ZX quote not in top 2: {[x.id for x in result.quotes[:3]]}"
        )

    def test_common_user_question_no_zx(self) -> None:
        """普通志愿问题不应错误召回 ZX 金句。"""
        r = _make_retriever()
        result = r.search("我580分湖北，想学计算机，有什么推荐？", {})
        zx_ids = [q.id for q in result.quotes if q.id.startswith("zx_")]
        # 普通问题不应该优先返回 ZX 金句（但可能因向量相似度误命中）
        # 检查是否排在 top-3 之外（即如果没有触发词，ZX 不应为主结果）
        assert not zx_ids, "Unexpected ZX quotes in normal query"

    def test_triggers_covered(self) -> None:
        """确认 _ZX_TRIGGERS 覆盖常用触发场景。"""
        assert "张雪峰" in _ZX_TRIGGERS, "张雪峰 should be a trigger"
        assert "演说家" in _ZX_TRIGGERS, "演说家 should be a trigger"
        assert "直播里讲" in _ZX_TRIGGERS, "直播里讲 should be a trigger"
        assert "讲座说过" in _ZX_TRIGGERS, "讲座说过 should be a trigger"

    def test_varied_zx_references_work(self) -> None:
        """多种明确提及张雪峰的触发词都应使 ZX 金句进入前3。"""
        r = _make_retriever()
        queries = [
            "雪峰老师说过什么？",
            "他在演说家里提过...",
        ]
        for query in queries:
            result = r.search(query, {})
            zx_ids = [q.id for q in result.quotes if q.id.startswith("zx_")]
            assert len(zx_ids) >= 1, f"Expected ZX quote for query: {query}"


class TestZxQuoteAttribution:
    """验证 ZX 金句的出处/年份信息可供后续使用。"""

    def test_source_attribution_available(self) -> None:
        """检索结果中的 ZX 金句应携带 source 和 year。"""
        r = _make_retriever()
        # 直接从内部列表找有出处的 ZX 金句
        sourced_quotes = [q for q in r._quotes if q.id.startswith("zx_") and q.source]
        assert len(sourced_quotes) >= 30, "Expected ≥30 ZX quotes with source"

    def test_top_quotes_serializable(self) -> None:
        """确认检索结果的 quotes 可序列化为 dict（兼容 RAG service）。"""
        r = _make_retriever()
        result = r.search("张雪峰怎么看计算机专业", {})
        for q in result.quotes:
            d = {
                "id": q.id,
                "text": q.text,
                "major": q.major,
                "tags": q.tags,
                "category": q.category,
                "sentiment": q.sentiment,
                "source": q.source,
                "year": q.year,
            }
            # 验证可 JSON 序列化
            payload = json.dumps(d, ensure_ascii=False)
            assert isinstance(payload, str)


class TestZxQuoteEdgeCases:
    """边界情况测试。"""

    def test_zx_quotes_not_in_general_search(self) -> None:
        """纯数据查询不应带回 ZX 金句。"""
        r = _make_retriever()
        queries = [
            "985大学有哪些",
            "山东省的位次怎么换算",
            "什么是冲稳保策略",
        ]
        for query in queries:
            result = r.search(query, {})
            zx_ids = [q.id for q in result.quotes if q.id.startswith("zx_")]
            assert not zx_ids, f"ZX quotes found in data query: {query}"

    def test_zhangxuefeng_originals_json_exists(self) -> None:
        """确认数据文件存在于正确位置。"""
        path = os.path.join(_QUOTES_DIR, "zhangxuefeng_originals.json")
        assert os.path.exists(path), "zhangxuefeng_originals.json not found"
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list), "Should be a JSON array"
        assert len(data) == 50, f"Expected 50 quotes, got {len(data)}"

    def test_zx_loading_independent_of_main_index(self) -> None:
        """CRITICAL 回归测试:ZX 文件加载不应依赖 _by_major.json。"""
        # 即使主索引不存在,ZX 文件也应被加载
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            # 只创建 ZX 文件,创建空的 quotes 目录(但放 ZX)
            os.makedirs(tmp, exist_ok=True)
            src = os.path.join(_QUOTES_DIR, "zhangxuefeng_originals.json")
            with open(src, encoding="utf-8") as f:
                zx_data = json.load(f)
            dst = os.path.join(tmp, "zhangxuefeng_originals.json")
            with open(dst, "w", encoding="utf-8") as f:
                json.dump(zx_data, f, ensure_ascii=False)
            # 不创建 _by_major.json
            r = KbRetriever(
                groups_dir=_GROUPS_DIR,
                quotes_path=tmp,
                embedding_provider=KeywordOnlyEmbedding(),
            )
            zx_ids = [q.id for q in r._quotes if q.id.startswith("zx_")]
            assert len(zx_ids) == 50, f"ZX file should load independently, got {len(zx_ids)}"
