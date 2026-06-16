"""Report generator — converts conversation data to Report.

Supports two modes:
1. From StructuredPlanningCard (when available from LangGraph state)
2. From slots + raw reply text (when card is not persisted)
"""

from __future__ import annotations

from typing import Any

from server.domain.schemas import StructuredPlanningCard
from server.report.models import Report


class ReportGenerator:
    """Generate a Report from conversation outputs."""

    @staticmethod
    def from_card(
        card: StructuredPlanningCard | None,
        session_id: str,
        slots: dict[str, Any],
        student_name: str | None = None,
    ) -> Report:
        """Build a Report from a StructuredPlanningCard + slot data.

        Args:
            card: The structured output from LangGraph (may be None if
                  not persisted — content will be populated by caller).
            session_id: Conversation session ID.
            slots: Extracted slot values {"province": "山东", "score": "600", ...}
            student_name: Optional student name for personalization.
        """
        def _extract(key: str) -> str:
            val = slots.get(key, "")
            if isinstance(val, dict):
                return str(val.get("value", ""))
            return str(val) if val else ""

        def _extract_int(key: str) -> int:
            val = _extract(key)
            try:
                return int(val.replace("分", "").strip())
            except (ValueError, TypeError):
                return 0

        if card is not None:
            # Mode 1: StructuredPlanningCard available
            return Report(
                session_id=session_id,
                student_name=student_name,
                province=_extract("province"),
                score=_extract_int("score"),
                subject=_extract("subject"),
                interest=_extract("interest"),
                summary=card.summary,
                facts=list(card.facts),
                suggestions=list(card.suggestions),
                risks=list(card.risks),
                next_actions=list(card.next_actions),
                confidence=card.confidence,
                scene=card.scene,
            )

        # Mode 2: No card — create Report with slot data only.
        # Content fields (summary, facts, suggestions, etc.) will be
        # populated by the caller from parsed reply text.
        return Report(
            session_id=session_id,
            student_name=student_name,
            province=_extract("province"),
            score=_extract_int("score"),
            subject=_extract("subject"),
            interest=_extract("interest"),
            summary="",
            facts=[],
            suggestions=[],
            risks=[],
            next_actions=[],
            confidence=0.0,
            scene="gaokao",
        )
