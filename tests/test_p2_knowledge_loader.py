"""Contextual knowledge loading tests — PUBLIC DEMO EDITION.

The private original shipped a ``knowledge/`` corpus (including a group
reproducing a named individual's methodology and a quotation file attributed
to that person) and this suite asserted keyword-trigger loading against it.

That corpus has no confirmed redistribution rights and is not shipped. The
loader remains in the codebase for the ``SkillService``/``KbRetriever`` path,
but with no corpus present it must return "nothing available" — and callers
must be able to tell that apart from "nothing matched".

``quality.knowledge_loader.load_contextual_knowledge`` returns ``None`` when
no knowledge applies. That ``None`` is indistinguishable from a silent failure
at the call site, which is precisely the degradation this demo avoids
elsewhere. The authoritative signal is ``server.services.rag.status()``.
"""

from __future__ import annotations

import pytest

from quality.knowledge_loader import load_contextual_knowledge
from server.services import rag


@pytest.fixture(autouse=True)
def _rag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_RAG_KB", "false")


class TestCorpusNotShipped:
    def test_knowledge_directory_absent(self) -> None:
        from pathlib import Path

        assert not (Path(__file__).resolve().parent.parent / "knowledge").exists()

    def test_legacy_knowledge_base_file_absent(self) -> None:
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        assert not (root / "knowledge_base.md").exists()


class TestLoaderReturnsNothingRatherThanInventing:
    """The loader must not fabricate content when the corpus is absent."""

    def test_returns_none_for_ai_era_query(self) -> None:
        assert load_contextual_knowledge("AI 时代还值得读大学吗") is None

    def test_returns_none_for_subject_selection(self) -> None:
        assert load_contextual_knowledge("新高考选科怎么选") is None

    def test_returns_none_for_vocational_query(self) -> None:
        assert load_contextual_knowledge(" vocational 策略") is None

    def test_respects_max_files(self) -> None:
        assert load_contextual_knowledge("就业", max_files=1) is None

    def test_accepts_slots_without_error(self) -> None:
        assert load_contextual_knowledge("就业", {"score": {"value": 600}}) is None

    def test_repeated_calls_are_stable(self) -> None:
        first = load_contextual_knowledge("就业")
        second = load_contextual_knowledge("就业")
        assert first == second


class TestUnavailabilityIsDiscoverable:
    """A None from the loader must be backed by a queryable status."""

    def test_status_is_authoritative(self) -> None:
        status = rag.status()
        assert status["state"] == "RAG_DISABLED"
        assert status["corpus_configured"] is False

    def test_status_reason_is_human_readable(self) -> None:
        reason = rag.status()["reason"]
        assert isinstance(reason, str)
        assert reason.strip()

    def test_enabling_without_corpus_still_reports_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Flipping the env var alone must not fake availability."""
        monkeypatch.setenv("ENABLE_RAG_KB", "true")
        status = rag.status()
        assert status["state"] == "RAG_DISABLED"
        assert status["corpus_configured"] is False
