"""
Quality orchestrator — runs the full quality pipeline.

Coordinates all 7 quality modules:
  1. emotion_detector — detect user emotion
  2. model_selector — select thinking models for the scenario
  3. decision_framework — recommend decision heuristics
  4. anti_pattern_checker — check AI output for anti-patterns
  5. ai_era_risk — assess AI-era risk for majors
  6. cross_validator — cross-validate admission data
  7. knowledge_loader — load contextual knowledge

Each sub-module is lazily initialized on first use.
"""

from __future__ import annotations

from typing import Any


class QualityOrchestrator:
    """Orchestrate the full quality pipeline across all 7 modules."""

    def __init__(self) -> None:
        # Lazy-init attributes
        self._model_selector_initialized = False
        self._decision_framework_initialized = False
        self._anti_pattern_checker_initialized = False
        self._emotion_detector_initialized = False
        self._ai_era_risk_initialized = False
        self._cross_validator_initialized = False
        self._knowledge_loader_initialized = False

    # ── Lazy properties ───────────────────────────────────────

    @property
    def model_selector(self) -> Any:
        if not self._model_selector_initialized:
            from quality import model_selector

            self._model_selector = model_selector
            self._model_selector_initialized = True
        return self._model_selector

    @property
    def decision_framework(self) -> Any:
        if not self._decision_framework_initialized:
            from quality import decision_framework

            self._decision_framework = decision_framework
            self._decision_framework_initialized = True
        return self._decision_framework

    @property
    def anti_pattern_checker(self) -> Any:
        if not self._anti_pattern_checker_initialized:
            from quality import anti_pattern_checker

            self._anti_pattern_checker = anti_pattern_checker
            self._anti_pattern_checker_initialized = True
        return self._anti_pattern_checker

    @property
    def emotion_detector(self) -> Any:
        if not self._emotion_detector_initialized:
            from quality import emotion_detector

            self._emotion_detector = emotion_detector
            self._emotion_detector_initialized = True
        return self._emotion_detector

    @property
    def ai_era_risk(self) -> Any:
        if not self._ai_era_risk_initialized:
            from quality import ai_era_risk

            self._ai_era_risk = ai_era_risk
            self._ai_era_risk_initialized = True
        return self._ai_era_risk

    @property
    def cross_validator(self) -> Any:
        if not self._cross_validator_initialized:
            from quality import cross_validator

            self._cross_validator = cross_validator
            self._cross_validator_initialized = True
        return self._cross_validator

    @property
    def knowledge_loader(self) -> Any:
        if not self._knowledge_loader_initialized:
            from quality import knowledge_loader

            self._knowledge_loader = knowledge_loader
            self._knowledge_loader_initialized = True
        return self._knowledge_loader

    # ── Pipeline methods ──────────────────────────────────────

    def detect_emotion(self, text: str) -> dict[str, Any]:
        """Detect user emotion."""
        return self.emotion_detector.detect_emotion(text)

    def select_models(
        self,
        slots: dict[str, Any],
        user_input: str = "",
    ) -> dict[str, Any]:
        """Select thinking models for the current scenario."""
        return self.model_selector.select_models(slots, user_input)

    def recommend_heuristics(
        self,
        slots: dict[str, Any],
        scenario: str | None = None,
    ) -> list[dict[str, Any]]:
        """Recommend decision heuristics."""
        return self.decision_framework.recommend_heuristics(slots, scenario)

    def check_anti_patterns(
        self,
        text: str,
        family_known: bool = False,
    ) -> list[dict[str, Any]]:
        """Check AI output for anti-patterns."""
        matches = self.anti_pattern_checker.check_anti_patterns(text, family_known)
        return [
            {
                "rule_id": m.rule_id,
                "pattern": m.pattern,
                "reason": m.reason,
                "fix": m.fix,
                "matched_text": m.matched_text,
                "severity": m.severity,
            }
            for m in matches
        ]

    def get_major_risk(self, major_name: str) -> dict[str, Any] | None:
        """Get AI-era risk assessment for a major."""
        return self.ai_era_risk.get_major_risk(major_name)

    def get_risk_summary(self, major_name: str) -> str | None:
        """Get a one-line risk summary for a major."""
        return self.ai_era_risk.get_risk_summary(major_name)

    def cross_validate(
        self,
        sources: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Cross-validate admission data from multiple sources."""
        return self.cross_validator.cross_validate_admission(sources)

    def load_knowledge(
        self,
        user_msg: str,
        slots: dict | None = None,
        max_files: int = 2,
    ) -> str | None:
        """Load contextual knowledge for the user query."""
        return self.knowledge_loader.load_contextual_knowledge(user_msg, slots, max_files)

    # ── Full pipeline ─────────────────────────────────────────

    def run_pre_generation_checks(
        self,
        user_msg: str,
        slots: dict[str, Any],
    ) -> dict[str, Any]:
        """Run all pre-generation quality checks.

        This is the main entry point for the quality pipeline before
        the AI generates a response.

        Returns:
            dict with emotion, model_selection, heuristics, knowledge
        """
        # 1. Detect emotion
        emotion = self.detect_emotion(user_msg)

        # 2. Select models
        model_selection = self.select_models(slots, user_msg)

        # 3. Recommend heuristics
        heuristics = self.recommend_heuristics(slots)

        # 4. Load contextual knowledge
        knowledge = self.load_knowledge(user_msg, slots)

        return {
            "emotion": emotion,
            "model_selection": model_selection,
            "heuristics": heuristics,
            "knowledge": knowledge,
        }

    def run_post_generation_checks(
        self,
        ai_output: str,
        family_known: bool = False,
    ) -> dict[str, Any]:
        """Run quality checks on AI-generated output.

        This is the main entry point for quality validation after
        the AI generates a response.

        Returns:
            dict with anti_patterns and should_rewrite flag
        """
        anti_patterns = self.check_anti_patterns(ai_output, family_known)
        from quality.anti_pattern_checker import get_error_count

        error_count = get_error_count(self.anti_pattern_checker.check_anti_patterns(ai_output, family_known))

        return {
            "anti_patterns": anti_patterns,
            "error_count": error_count,
            "should_rewrite": error_count >= 1,
        }
