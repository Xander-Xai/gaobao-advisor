"""Tests for skills/service.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from skills.service import SkillService

_SKILL_ASSETS_AVAILABLE = (Path(__file__).parent.parent / "skills/gaokao/mental_models.md").exists()
requires_restricted_skill_assets = pytest.mark.skipif(
    not _SKILL_ASSETS_AVAILABLE,
    reason="restricted methodology assets are intentionally absent from the public distribution",
)


@pytest.fixture
def service() -> SkillService:
    """Create a SkillService with the real skills directory."""
    return SkillService(skills_dir=Path(__file__).parent.parent / "skills")


@requires_restricted_skill_assets
class TestLoadAssets:
    """Tests for load_assets functionality."""

    def test_load_assets(self, service: SkillService) -> None:
        """Loading populates all skill texts, >100 chars each."""
        service.load_assets()

        # All skill files should be loaded with substantial content
        assert len(service._mental_models) > 100, "mental_models should be >100 chars"
        assert len(service._heuristics_text) > 100, "heuristics should be >100 chars"
        assert len(service._anti_patterns) > 100, "anti_patterns should be >100 chars"
        assert len(service._expression_engine) > 100, "expression_engine should be >100 chars"
        assert len(service._safety_rules) > 100, "safety_rules should be >100 chars"

    def test_load_assets_idempotent(self, service: SkillService) -> None:
        """Loading twice doesn't reload."""
        service.load_assets()

        # Modify the content after first load
        service._mental_models = "modified content"

        # Second load should not reload
        service.load_assets()
        assert service._mental_models == "modified content"
        assert service._loaded is True


@requires_restricted_skill_assets
class TestBuildContext:
    """Tests for build_context functionality."""

    def test_build_context_gaokao(self, service: SkillService) -> None:
        """Context contains key skill content for gaokao scene."""
        context = service.build_context("gaokao")

        # Check for key phrases from the skill files
        assert "社会筛子论" in context, "Should contain 社会筛子论"
        assert "就业倒推法" in context, "Should contain 就业倒推法"
        assert "阶层现实主义" in context, "Should contain 阶层现实主义"
        assert "灵魂追问" in context, "Should contain 灵魂追问"
        assert "反问开场" in context, "Should contain 反问开场"

    def test_build_context_general_fallback(self, service: SkillService) -> None:
        """Unknown scene returns non-crash (graceful fallback)."""
        # Should not raise exception for unknown scenes
        context = service.build_context("unknown_scene")
        # Should return empty or mental_models only
        assert isinstance(context, str)

    def test_build_context_contains_safety(self, service: SkillService) -> None:
        """Context has safety-related content."""
        context = service.build_context("gaokao")

        # Safety rules should be included
        assert "身份锁定" in context or "安全" in context, "Context should contain safety-related content"


class TestBuildStrategy:
    """Tests for build_strategy functionality."""

    def test_build_strategy_gaokao(self, service: SkillService) -> None:
        """Strategy has heuristics, output_style, answer_rules."""
        strategy = service.build_strategy("gaokao")

        assert strategy.scene == "gaokao"
        assert len(strategy.heuristics) > 0, "Should have heuristics"
        assert len(strategy.output_style) > 0, "Should have output_style"
        assert len(strategy.answer_rules) > 0, "Should have answer_rules"

        # Check specific content
        assert any("灵魂追问" in h for h in strategy.heuristics)
        assert any("直接" in s for s in strategy.output_style)
        assert any("数据库" in r for r in strategy.answer_rules)

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

        # Should mention at least one missing field
        assert "省份" in reply or "分数" in reply
        # Should have a lead phrase
        assert "你别急" in reply or "先别" in reply

    def test_build_question_reply_empty_fields(self, service: SkillService) -> None:
        """Reply handles empty missing_fields gracefully."""
        reply = service.build_question_reply("gaokao", [])

        assert isinstance(reply, str)
        assert len(reply) > 0

    def test_build_question_reply_kaoyan_scene(self, service: SkillService) -> None:
        """Reply uses correct lead for kaoyan scene."""
        reply = service.build_question_reply("kaoyan", ["score"])

        assert "考研" in reply or "先别" in reply


class TestMissingSkillsDir:
    """Tests for missing skills directory fallback."""

    def test_missing_skills_dir_fallback(self, tmp_path: Path) -> None:
        """Nonexistent skills dir doesn't crash."""
        service = SkillService(skills_dir=tmp_path / "nonexistent")

        # Should not raise exception
        service.load_assets()

        # All texts should be empty (files don't exist)
        assert service._mental_models == ""
        assert service._heuristics_text == ""
        assert service._anti_patterns == ""
        assert service._expression_engine == ""
        assert service._safety_rules == ""

        # build_context should return empty string (no loaded files)
        context = service.build_context("gaokao")
        assert context == ""

        # build_strategy still returns hardcoded gaokao strategy (by design)
        # even when files are missing, strategy is module-level constant
        strategy = service.build_strategy("gaokao")
        assert strategy.scene == "gaokao"
        assert len(strategy.heuristics) == 8  # Hardcoded constants
