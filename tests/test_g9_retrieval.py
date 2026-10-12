"""G9 persona-methodology retrieval tests — PUBLIC DEMO EDITION.

The private original carried ``knowledge/groups/G9_zhangxuefeng_methodology_origin.md``
and this suite asserted that the G9 group was retrievable and that its triggers
fired on mentions of that individual.

G9 is a reproduction of a named person's methodology. It is not redistributed
here, so the retrieval path must report *unavailable* rather than returning an
empty-but-successful result. These tests pin that contract.
"""

from __future__ import annotations

import os

import pytest

from server.services import rag


@pytest.fixture(autouse=True)
def _rag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test in this module runs with RAG disabled, as shipped."""
    monkeypatch.setenv("ENABLE_RAG_KB", "false")


class TestCorpusAbsent:
    def test_groups_directory_not_shipped(self) -> None:
        from pathlib import Path

        assert not (Path(__file__).resolve().parent.parent / "knowledge").exists(), (
            "no knowledge corpus may be present in the public demo"
        )

    def test_g9_group_absent(self) -> None:
        from pathlib import Path

        g9 = Path(__file__).resolve().parent.parent / "knowledge" / "groups"
        assert not (g9 / "G9_zhangxuefeng_methodology_origin.md").exists()


class TestRetrievalIsDisabledNotEmpty:
    """The key contract: unavailable retrieval must not look like success."""

    def test_status_reports_disabled(self) -> None:
        status = rag.status()
        assert status["state"] == "RAG_DISABLED"
        assert status["reason"], "a disabled state must carry an explanation"

    def test_search_raises_instead_of_returning_empty(self) -> None:
        """The exact bug this guards: empty result read as 'nothing found'."""
        with pytest.raises(rag.RagDisabledError):
            rag.search("就业前景怎么样", {})

    def test_configure_refused_while_disabled(self) -> None:
        with pytest.raises(rag.RagDisabledError):
            rag.configure("knowledge/groups", "knowledge/quotes/_index.json")

    def test_is_available_is_false(self) -> None:
        assert rag.is_available() is False


class TestRagNodeReportsDisabled:
    def test_rag_node_marks_disabled(self) -> None:
        from server.graph.nodes.rag_node import rag_retrieve_node

        out = rag_retrieve_node({"input_text": "帮我看看就业", "slots": {}, "trace": []})
        assert out["rag_state"] == "RAG_DISABLED"
        assert out["rag_reason"]
        assert out["knowledge_context"] == ""
        # The trace must carry the state so it cannot be silently dropped.
        assert any(e.get("event") == "RAG_DISABLED" for e in out["trace"])

    def test_health_surfaces_rag_state(self) -> None:
        """Health must never report ok while retrieval is unavailable."""
        import asyncio

        from server.routes.health import health_check

        payload = asyncio.run(health_check())
        assert payload["optional_services"]["rag"]["state"] == "RAG_DISABLED"
        assert "rag" in payload["degraded_services"]
        assert payload["data_profile"] == "SYNTHETIC_DEMO"


class TestEnvironmentHonesty:
    def test_env_example_disables_rag(self) -> None:
        from pathlib import Path

        env = (Path(__file__).resolve().parent.parent / ".env.example").read_text(encoding="utf-8")
        line = next(ln for ln in env.splitlines() if ln.strip().startswith("ENABLE_RAG_KB"))
        assert line.split("=", 1)[1].strip() == "false", "shipped config must match shipped behaviour"

    def test_config_defaults_to_disabled(self) -> None:
        monkey = os.environ.get("ENABLE_RAG_KB", "")
        assert monkey.lower() not in ("true", "1", "yes"), (
            "test environment must not enable a corpus that does not exist"
        )
