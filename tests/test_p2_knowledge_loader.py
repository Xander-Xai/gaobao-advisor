"""Contextual knowledge loading tests — PUBLIC DEMO EDITION (synthetic corpus).

The private original shipped a ``knowledge/`` corpus (including a group
reproducing a named individual's methodology and a quotation file attributed
to that person) and this suite asserted keyword-trigger loading against it.

The public demo ships an original, synthetic, marked corpus instead. The
legacy keyword-trigger loader (``quality.knowledge_loader``) points at the old
``knowledge/*.md`` filenames, which are **not** shipped, so it returns "nothing
available"; the real retrieval path goes through ``KbRetriever`` /
``server.services.rag`` and is the authoritative signal.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quality.knowledge_loader import load_contextual_knowledge
from server.services import rag

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _fresh_rag(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ENABLE_RAG_KB", raising=False)
    rag.reset()
    yield
    rag.reset()


class TestSyntheticCorpusShipped:
    def test_synthetic_corpus_present(self) -> None:
        assert (REPO_ROOT / "knowledge" / "synthetic_demo" / "groups").is_dir()

    def test_legacy_knowledge_base_file_absent(self) -> None:
        assert not (REPO_ROOT / "knowledge_base.md").exists()

    def test_legacy_trigger_files_not_shipped(self) -> None:
        # The old keyword-trigger filenames are not part of the synthetic corpus.
        assert not (REPO_ROOT / "knowledge" / "00_ai_era_correction.md").exists()


class TestLegacyLoaderReturnsNothingRatherThanInventing:
    """The legacy loader must not fabricate content when its files are absent."""

    def test_returns_none_for_ai_era_query(self) -> None:
        assert load_contextual_knowledge("AI 时代还值得读大学吗") is None

    def test_returns_none_for_subject_selection(self) -> None:
        assert load_contextual_knowledge("新高考选科怎么选") is None

    def test_respects_max_files(self) -> None:
        assert load_contextual_knowledge("就业", max_files=1) is None

    def test_accepts_slots_without_error(self) -> None:
        assert load_contextual_knowledge("就业", {"score": {"value": 600}}) is None

    def test_repeated_calls_are_stable(self) -> None:
        assert load_contextual_knowledge("就业") == load_contextual_knowledge("就业")


class TestLoaderUsesRetrieverWhenProvided:
    def test_returns_content_for_known_query(self) -> None:
        assert rag.initialize_default() is True
        retriever = rag._get_retriever()
        out = load_contextual_knowledge("平行志愿的投档规则", kb_retriever=retriever)
        assert out, "the retriever path must return synthetic corpus content"
        assert "平行志愿" in out or "投档" in out


class TestStatusIsAuthoritative:
    def test_status_reflects_real_availability(self) -> None:
        assert rag.initialize_default() is True
        status = rag.status()
        assert status["state"] == "RAG_ENABLED"
        assert status["corpus_configured"] is True
        assert status["documents"] >= 1

    def test_disabled_switch_is_reported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENABLE_RAG_KB", "false")
        status = rag.status()
        assert status["state"] == "RAG_DISABLED"
        assert status["reason"].strip()
