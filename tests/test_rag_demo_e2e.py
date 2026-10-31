"""End-to-end acceptance tests for the default SYNTHETIC_DEMO RAG demo.

These map to the ten acceptance criteria for turning RAG from an optional,
disabled capability into a working, testable, citable retrieval capability in
the default demo environment:

1. default startup succeeds and reports a real RAG state
2. RAG health is genuinely available
3. a known synthetic-knowledge question returns non-empty evidence
4. the answer/response carries valid source citations
5. no matching evidence means "cannot verify", not a fabricated conclusion
6. removing the corpus produces an explicit failure state (fail closed)
7. SQL vs RAG vs mixed questions route correctly
8. different sessions do not contaminate each other
9. the basic demo completes with no external API key
10. no unauthorised paid API request is made
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.services import rag

REPO_ROOT = Path(__file__).resolve().parent.parent
EVAL_PATH = REPO_ROOT / "knowledge" / "synthetic_demo" / "eval_queries.json"


@pytest.fixture(autouse=True)
def _no_keys(monkeypatch: pytest.MonkeyPatch):
    """Run as an offline, key-less deployment unless a test says otherwise."""
    for key in (
        "ENABLE_RAG_KB",
        "SILICONFLOW_API_KEY",
        "OPENAI_API_KEY",
        "DASHSCOPE_API_KEY",
        "RAG_EMBEDDING_PROVIDER",
    ):
        monkeypatch.delenv(key, raising=False)
    rag.reset()
    yield
    rag.reset()


# ── 1 & 2. Default startup + real health state ───────────────────────────
class TestDefaultStartupAndHealth:
    def test_lifespan_brings_rag_up(self) -> None:
        from server.main import app

        with TestClient(app) as client:
            body = client.get("/api/v1/health").json()
        assert body["data_profile"] in {"SYNTHETIC_DEMO", "EMPTY"}
        assert body["optional_services"]["rag"]["state"] == "RAG_ENABLED"
        assert body["optional_services"]["rag"]["integrity_ok"] is True
        assert body["optional_services"]["rag"]["documents"] >= 1

    def test_health_endpoint_reports_availability(self) -> None:
        from server.main import app

        with TestClient(app) as client:
            resp = client.get("/api/v1/health")
        assert resp.status_code == 200


# ── 3 & 4. Known question → evidence + citations ─────────────────────────
class TestEvidenceAndCitations:
    def test_known_question_returns_evidence_via_service(self) -> None:
        assert rag.initialize_default() is True
        result = rag.search("平行志愿的投档规则是什么", {})
        assert result["has_evidence"] is True
        assert result["group_chunks"]

    def test_known_question_returns_evidence_via_endpoint(self) -> None:
        from server.main import app

        with TestClient(app) as client:
            resp = client.post("/api/v1/knowledge/search", json={"query": "平行志愿的投档规则是什么"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_evidence"] is True
        assert body["count"] >= 1
        assert body["citations"], "evidence must carry citations"
        assert all(c.get("source") for c in body["citations"])
        assert all(c.get("chunk_id") for c in body["citations"])

    def test_chat_stream_emits_sources_event(self) -> None:
        from server.main import app

        with TestClient(app) as client:
            with client.stream(
                "POST",
                "/api/v1/chat",
                json={"session_id": "e2e-sources", "scene": "gaokao", "message": "平行志愿的投档规则是什么"},
            ) as resp:
                payload = "".join(resp.iter_text())
        assert '"type": "sources"' in payload
        assert "G1_core_method" in payload


# ── 5. No evidence → no fabrication ──────────────────────────────────────
class TestNoEvidenceMeansCannotVerify:
    def test_off_domain_query_returns_no_evidence(self) -> None:
        assert rag.initialize_default() is True
        result = rag.search("量子缠结与超导磁悬浮技术前沿", {})
        assert result["has_evidence"] is False
        assert result["group_chunks"] == []

    def test_off_domain_endpoint_reports_no_evidence(self) -> None:
        from server.main import app

        with TestClient(app) as client:
            resp = client.post("/api/v1/knowledge/search", json={"query": "量子缠结与超导磁悬浮技术前沿"})
        assert resp.status_code == 200
        assert resp.json()["has_evidence"] is False

    def test_llm_context_forbids_fabrication_without_evidence(self) -> None:
        from server.agent.llm_reliability import build_llm_context

        context = build_llm_context(
            {
                "reasoning": "暂无足够信息",
                "rag_state": "RAG_ENABLED",
                "rag_evidence": False,
                "rag_sources": [],
            }
        )
        assert "无法验证" in context or "未检索到" in context
        assert "严禁编造" in context or "不得" in context

    def test_rag_node_marks_no_evidence(self) -> None:
        from server.graph.nodes.rag_node import rag_retrieve_node

        assert rag.initialize_default() is True
        out = rag_retrieve_node({"input_text": "量子缠结与超导磁悬浮技术前沿", "slots": {}, "trace": []})
        assert out["rag_state"] == "RAG_ENABLED"
        assert out["rag_evidence"] is False
        assert out["knowledge_context"] == ""
        assert out["rag_sources"] == []


# ── 6. Corpus removal → explicit failure ─────────────────────────────────
class TestCorpusRemovalFailsClosed:
    def test_removed_corpus_is_runtime_error(self, tmp_path: Path) -> None:
        import shutil

        groups = tmp_path / "groups"
        groups.mkdir()
        (groups / "G1.md").write_text(f"<!-- {rag.CORPUS_MARKER} -->\n## s\ncontent\n", encoding="utf-8")
        quotes = tmp_path / "quotes"
        quotes.mkdir()
        rag.configure(str(groups), str(quotes))
        shutil.rmtree(groups)

        assert rag.status()["state"] == "RAG_ERROR"
        with pytest.raises(rag.RagCorpusError):
            rag.search("平行志愿", {})

    def test_corrupt_corpus_is_runtime_error(self, tmp_path: Path) -> None:
        groups = tmp_path / "groups"
        groups.mkdir()
        (groups / "G1.md").write_text("# no marker\n## s\ncontent\n", encoding="utf-8")
        quotes = tmp_path / "quotes"
        quotes.mkdir()
        with pytest.raises(rag.RagCorpusError):
            rag.configure(str(groups), str(quotes))
        assert rag.status()["state"] == "RAG_ERROR"

    def test_endpoint_reports_503_when_broken(self, tmp_path: Path) -> None:
        from server.main import app

        groups = tmp_path / "groups"
        groups.mkdir()
        (groups / "G1.md").write_text("# no marker\n## s\ncontent\n", encoding="utf-8")
        quotes = tmp_path / "quotes"
        quotes.mkdir()
        with pytest.raises(rag.RagCorpusError):
            rag.configure(str(groups), str(quotes))

        # No lifespan here: exercise the endpoint against the already-broken
        # configuration so the fail-closed path is what gets tested.
        client = TestClient(app)
        resp = client.post("/api/v1/knowledge/search", json={"query": "平行志愿"})
        assert resp.status_code == 503


# ── 7. SQL vs RAG vs mixed routing ───────────────────────────────────────
class TestRouting:
    def _events(self, result: dict) -> set[str]:
        return {e.get("node") for e in result.get("trace", [])}

    def test_pure_knowledge_question_uses_rag_not_profile_questions(self) -> None:
        from server.graph.graph import build_advisor_graph

        assert rag.initialize_default() is True
        graph = build_advisor_graph()
        result = graph.invoke(
            {"input_text": "平行志愿的投档规则是什么", "scene": "gaokao", "session_id": "e2e-rag", "slots": {}}
        )
        nodes = self._events(result)
        assert "rag_retrieve" in nodes
        assert "question_generate" not in nodes, "a knowledge question must not be turned into a profile question"

    def test_mixed_question_runs_both_data_and_rag(self) -> None:
        from server.graph.graph import build_advisor_graph

        assert rag.initialize_default() is True
        graph = build_advisor_graph()
        result = graph.invoke(
            {
                "input_text": "我是示例省·甲的物理类考生，600分，想报计算机专业，平行志愿投档规则是什么",
                "scene": "gaokao",
                "session_id": "e2e-mixed",
                "slots": {
                    "province": "示例省·甲",
                    "score": 600,
                    "score_rank": 20000,
                    "subject": "物理",
                    "interest": "计算机科学与技术（合成）",
                },
            }
        )
        nodes = self._events(result)
        assert "data_query" in nodes, "structured query path must run"
        assert "rag_retrieve" in nodes, "knowledge path must run"
        assert result.get("rag_evidence") is True


# ── 8. Session isolation ─────────────────────────────────────────────────
class TestSessionIsolation:
    def test_two_sessions_do_not_share_profile_slots(self) -> None:
        from server.graph.graph import build_advisor_graph

        assert rag.initialize_default() is True
        graph = build_advisor_graph()
        a = graph.invoke(
            {
                "input_text": "我是示例省·甲的物理类考生，600分，想报计算机",
                "scene": "gaokao",
                "session_id": "e2e-iso-a",
                "slots": {
                    "province": "示例省·甲",
                    "score": 600,
                    "score_rank": 20000,
                    "subject": "物理",
                    "interest": "计算机",
                },
            }
        )
        b = graph.invoke(
            {
                "input_text": "我是示例省·乙的历史类考生，580分，想报汉语言文学",
                "scene": "gaokao",
                "session_id": "e2e-iso-b",
                "slots": {
                    "province": "示例省·乙",
                    "score": 580,
                    "score_rank": 30000,
                    "subject": "历史",
                    "interest": "汉语言文学",
                },
            }
        )
        assert a["slots"].get("province") == "示例省·甲"
        assert b["slots"].get("province") == "示例省·乙"
        assert a["slots"].get("province") != b["slots"].get("province")
        # The knowledge corpus is shared (it is not user data), but each
        # response's citations must come from that shared corpus, not from the
        # other session's profile.
        for result in (a, b):
            for source in result.get("rag_sources", []):
                assert "示例省" not in json.dumps(source, ensure_ascii=False)


# ── 9 & 10. No key, no paid request ──────────────────────────────────────
class TestOfflineNoKey:
    def test_default_provider_is_local_keyword(self) -> None:
        assert rag._default_provider() == "keyword"

    def test_retriever_uses_keyword_embedding_without_keys(self) -> None:
        from server.services.kb_retriever import KeywordOnlyEmbedding

        assert rag.initialize_default() is True
        retriever = rag._get_retriever()
        assert isinstance(retriever._embedder, KeywordOnlyEmbedding)
        assert rag.status()["provider"] == "keyword"

    def test_basic_demo_works_without_any_key(self) -> None:
        from server.main import app

        with TestClient(app) as client:
            search = client.post("/api/v1/knowledge/search", json={"query": "冲稳保怎么分配"}).json()
            health = client.get("/api/v1/health").json()
        assert search["has_evidence"] is True
        assert health["optional_services"]["rag"]["state"] == "RAG_ENABLED"


# ── Minimal RAG quality evaluation (real measurement, no invented numbers) ─
class TestMinimalRagEvaluation:
    def test_group_hit_rate_on_labeled_set(self) -> None:
        assert rag.initialize_default() is True
        retriever = rag._get_retriever()
        data = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
        queries = data["queries"]
        hits = 0
        for item in queries:
            result = retriever.search(item["query"], {})
            if any(g in result.groups for g in item["expected_groups"]):
                hits += 1
        rate = hits / len(queries)
        print(f"\nRAG labeled-set group hit-rate: {hits}/{len(queries)} = {rate:.3f}")
        assert rate >= 0.75, f"retrieval degraded: hit-rate {rate:.3f}"
