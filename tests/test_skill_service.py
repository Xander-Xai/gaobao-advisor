"""Tests for skills/service.py — PUBLIC DEMO EDITION.

Change log vs. the private original:

* The persona-mimicry assets (``expression_engine.md``, ``expression_samples.md``)
  and the named-individual methodology assets are **not redistributed** here.
  Tests that asserted their presence were replaced with assertions that the
  demo does not depend on them.
* ``test_missing_skills_dir_fallback`` was **inverted**. The original asserted
  that a missing skills directory loads nothing and still returns a strategy —
  i.e. it enshrined a fail-open path in which ``safety_rules.md`` is silently
  dropped and an answer is produced with no safety constraints. The public demo
  fails closed instead, and this suite now pins that behaviour.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from skills.service import REQUIRED_SKILL_FILES, SkillAssetUnavailableError, SkillService


@pytest.fixture
def service() -> SkillService:
    """Create a SkillService with the real skills directory."""
    return SkillService(skills_dir=Path(__file__).parent.parent / "skills")


class TestLoadAssets:
    """Tests for load_assets functionality."""

    def test_load_assets(self, service: SkillService) -> None:
        """Loading populates the safety rules with substantial content."""
        service.load_assets()

        # Safety rules are the mandatory asset and must always be substantial.
        assert len(service._safety_rules) > 100, "safety_rules should be >100 chars"

    def test_load_assets_idempotent(self, service: SkillService) -> None:
        """Loading twice doesn't reload."""
        service.load_assets()

        # Modify the content after first load
        service._safety_rules = "modified content"

        # Second load should not reload
        service.load_assets()
        assert service._safety_rules == "modified content"
        assert service._loaded is True

    def test_expression_engine_not_shipped(self, service: SkillService) -> None:
        """The persona-mimicry style engine is not part of the public demo."""
        gaokao_dir = Path(__file__).parent.parent / "skills" / "gaokao"
        assert not (gaokao_dir / "expression_engine.md").exists()
        assert not (gaokao_dir / "expression_samples.md").exists()


class TestBuildContext:
    """Tests for build_context functionality."""

    def test_build_context_gaokao(self, service: SkillService) -> None:
        """Context always contains the mandatory safety rules."""
        context = service.build_context("gaokao")
        assert context.strip(), "context must never be empty"
        assert "safety rules" in context.lower() or "安全" in context

    def test_build_context_general_fallback(self, service: SkillService) -> None:
        """Unknown scene returns non-crash (graceful fallback)."""
        context = service.build_context("unknown_scene")
        assert isinstance(context, str)
        # Even for an unknown scene, the safety rules must still be present.
        assert context.strip(), "safety rules must be injected for every scene"

    def test_build_context_contains_safety(self, service: SkillService) -> None:
        """Context has safety-related content."""
        context = service.build_context("gaokao")

        for expected in ("No fabricated facts", "Prompt injection", "synthetic"):
            assert expected in context, f"Context should contain {expected!r}"


class TestBuildStrategy:
    """Tests for build_strategy functionality."""

    def test_build_strategy_gaokao(self, service: SkillService) -> None:
        """Strategy has heuristics, output_style, answer_rules."""
        strategy = service.build_strategy("gaokao")

        assert strategy.scene == "gaokao"
        assert len(strategy.heuristics) > 0, "Should have heuristics"
        assert len(strategy.output_style) > 0, "Should have output_style"
        assert len(strategy.answer_rules) > 0, "Should have answer_rules"

        # The demo must not instruct the model to mimic a specific person.
        joined = " ".join(strategy.output_style)
        assert "模仿特定人物" not in joined or "不使用" in joined

    def test_build_strategy_unknown_scene(self, service: SkillService) -> None:
        """Unknown scene returns empty strategy (no crash)."""
        strategy = service.build_strategy("unknown_scene")

        assert strategy.scene == "unknown_scene"
        assert strategy.heuristics == []
        assert strategy.output_style == []
        assert strategy.answer_rules == []


class TestBuildQuestionReply:
    """Tests for build_question_reply functionality."""

    def test_build_question_reply(self, service: SkillService) -> None:
        """Reply mentions missing fields."""
        reply = service.build_question_reply("gaokao", ["province", "score"])

        assert "省份" in reply or "分数" in reply

    def test_build_question_reply_empty_fields(self, service: SkillService) -> None:
        """Reply handles empty missing_fields gracefully."""
        reply = service.build_question_reply("gaokao", [])

        assert isinstance(reply, str)
        assert len(reply) > 0

    def test_build_question_reply_kaoyan_scene(self, service: SkillService) -> None:
        """Reply uses correct lead for kaoyan scene."""
        reply = service.build_question_reply("kaoyan", ["score"])

        assert isinstance(reply, str)
        assert len(reply) > 0


class TestFailClosed:
    """Negative-control tests: the service must refuse to run unguarded.

    These replace the original ``test_missing_skills_dir_fallback``, which
    asserted the opposite (fail-open) behaviour.
    """

    def test_missing_skills_dir_raises(self, tmp_path: Path) -> None:
        """A missing skills directory disables answer generation."""
        service = SkillService(skills_dir=tmp_path / "nonexistent")

        with pytest.raises(SkillAssetUnavailableError):
            service.load_assets()

        with pytest.raises(SkillAssetUnavailableError):
            service.build_context("gaokao")

    def test_missing_safety_rules_raises(self, tmp_path: Path) -> None:
        """Missing safety_rules.md disables answer generation."""
        skills_dir = tmp_path / "skills"
        gaokao_dir = skills_dir / "gaokao"
        gaokao_dir.mkdir(parents=True)
        # Deliberately omit safety_rules.md.
        (gaokao_dir / "heuristics.md").write_text("some heuristics", encoding="utf-8")

        service = SkillService(skills_dir=skills_dir)
        with pytest.raises(SkillAssetUnavailableError, match="safety_rules"):
            service.build_context("gaokao")

    def test_empty_safety_rules_raises(self, tmp_path: Path) -> None:
        """An empty safety_rules.md also disables answer generation."""
        skills_dir = tmp_path / "skills"
        gaokao_dir = skills_dir / "gaokao"
        gaokao_dir.mkdir(parents=True)
        (gaokao_dir / "safety_rules.md").write_text("   \n", encoding="utf-8")

        service = SkillService(skills_dir=skills_dir)
        with pytest.raises(SkillAssetUnavailableError, match="empty"):
            service.build_context("gaokao")

    def test_required_files_are_declared(self) -> None:
        """The mandatory asset list is not empty."""
        assert REQUIRED_SKILL_FILES == ("safety_rules.md",)
