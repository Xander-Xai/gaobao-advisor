"""RAG availability tests — PUBLIC DEMO EDITION (synthetic corpus enabled).

The upstream private project shipped ``knowledge/groups/G9_zhangxuefeng_methodology_origin.md``
and this suite asserted that the G9 persona group was retrievable. That corpus
reproduces a named person's methodology and is **not** redistributed here.

What ships instead is an original **SYNTHETIC_DEMO** corpus. In the default
demo environment RAG is enabled against it and retrieval returns real,
citable evidence. These tests pin that contract, the persona-corpus exclusion,
and the fail-closed behaviour when the corpus is missing or unmarked.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from server.services import rag

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _fresh_rag(monkeypatch: pytest.MonkeyPatch):
    """Run each test from a clean RAG state with the default (enabled) switch."""
    monkeypatch.delenv("ENABLE_RAG_KB", raising=False)
    rag.reset()
    yield
    rag.reset()


class TestPersonaCorpusAbsent:
    def test_g9_persona_group_absent(self) -> None:
        legacy = REPO_ROOT / "knowledge" / "groups"
        assert not (legacy / "G9_zhangxuefeng_methodology_origin.md").exists()

    def test_no_persona_named_file_in_corpus(self) -> None:
        offenders = [
            str(p)
            for p in (REPO_ROOT / "knowledge").rglob("*")
            if any(t in p.name.lower() for t in ("zhangxuefeng", "xuefeng", "雪峰"))
        ]
        assert offenders == [], f"persona assets must not ship: {offenders}"


class TestSyntheticCorpusShipped:
    def test_corpus_present_and_marked(self) -> None:
        groups = REPO_ROOT / "knowledge" / "synthetic_demo" / "groups"
        assert groups.is_dir(), "the synthetic demo corpus must ship"
        files = sorted(groups.glob("*.md"))
        assert files, "the synthetic demo corpus must contain group files"
        for path in files:
            text = path.read_text(encoding="utf-8")
            assert rag.CORPUS_MARKER in text, f"{path.name} must carry the SYNTHETIC_DEMO marker"

    def test_manifest_marker(self) -> None:
        import json

        manifest = json.loads((REPO_ROOT / "knowledge" / "synthetic_demo" / "manifest.json").read_text("utf-8"))
        assert manifest["marker"] == rag.CORPUS_MARKER
        assert manifest["license"] == "CC0-1.0"


class TestRagDefaultEnabled:
    def test_defaults_on_and_initializes(self) -> None:
        assert rag._enabled() is True
        assert rag.initialize_default() is True
        status = rag.status()
        assert status["state"] == "RAG_ENABLED"
        assert status["documents"] >= 1
        assert status["integrity_ok"] is True

    def test_known_question_returns_evidence_and_citations(self) -> None:
        assert rag.initialize_default() is True
        result = rag.search("平行志愿的投档规则是什么", {})
        assert result["has_evidence"] is True
        assert result["group_chunks"], "a known synthetic question must return evidence"
        assert result["citations"], "evidence must carry citations"
        assert all(c["source"] for c in result["citations"])

    def test_off_domain_question_returns_no_evidence(self) -> None:
        assert rag.initialize_default() is True
        result = rag.search("量子缠结与超导磁悬浮技术前沿", {})
        assert result["has_evidence"] is False
        assert result["group_chunks"] == []


class TestFailClosed:
    def test_missing_corpus_reports_error(self, tmp_path: Path) -> None:
        groups = tmp_path / "groups"
        groups.mkdir()
        (groups / "G1.md").write_text(f"<!-- {rag.CORPUS_MARKER} -->\n## s\ncontent\n", encoding="utf-8")
        quotes = tmp_path / "quotes"
        quotes.mkdir()
        rag.configure(str(groups), str(quotes))
        assert rag.status()["state"] == "RAG_ENABLED"

        # Remove the corpus out from under the running configuration.
        import shutil

        shutil.rmtree(groups)
        assert rag.status()["state"] == "RAG_ERROR"
        with pytest.raises(rag.RagCorpusError):
            rag.search("平行志愿", {})

    def test_unmarked_corpus_rejected(self, tmp_path: Path) -> None:
        groups = tmp_path / "groups"
        groups.mkdir()
        (groups / "G1.md").write_text("# unmarked\n## s\ncontent\n", encoding="utf-8")
        quotes = tmp_path / "quotes"
        quotes.mkdir()
        with pytest.raises(rag.RagCorpusError):
            rag.configure(str(groups), str(quotes))
        assert rag.status()["state"] == "RAG_ERROR"

    def test_disabled_switch_reports_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENABLE_RAG_KB", "false")
        assert rag.status()["state"] == "RAG_DISABLED"
        with pytest.raises(rag.RagDisabledError):
            rag.search("就业前景怎么样", {})


class TestRagNodeSurface:
    def test_node_reports_evidence(self) -> None:
        from server.graph.nodes.rag_node import rag_retrieve_node

        assert rag.initialize_default() is True
        out = rag_retrieve_node({"input_text": "平行志愿的投档规则", "slots": {}, "trace": []})
        assert out["rag_state"] == "RAG_ENABLED"
        assert out["rag_evidence"] is True
        assert out["knowledge_context"]
        assert out["rag_sources"]

    def test_health_surfaces_rag_state(self) -> None:
        import asyncio

        from server.routes.health import health_check

        assert rag.initialize_default() is True
        payload = asyncio.run(health_check())
        assert payload["optional_services"]["rag"]["state"] == "RAG_ENABLED"
        assert payload["optional_services"]["rag"]["documents"] >= 1
        assert payload["data_profile"] == "SYNTHETIC_DEMO"


class TestEnvironmentHonesty:
    def test_env_example_enables_rag(self) -> None:
        env = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
        line = next(ln for ln in env.splitlines() if ln.strip().startswith("ENABLE_RAG_KB"))
        assert line.split("=", 1)[1].strip() == "true", "shipped config must match shipped behaviour"

    def test_entrypoint_defaults_rag_on(self) -> None:
        script = (REPO_ROOT / "docker-entrypoint.sh").read_text(encoding="utf-8")
        assert 'ENABLE_RAG_KB="${ENABLE_RAG_KB:-true}"' in script
