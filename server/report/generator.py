"""Report generator — converts StructuredPlanningCard to Report."""

from __future__ import annotations

from typing import Any

from server.domain.schemas import StructuredPlanningCard
from server.report.models import Report


class ReportGenerator:
    """Generate a Report from conversation outputs."""

    @staticmethod
    def from_card(
        card: StructuredPlanningCard,
        session_id: str,
        slots: dict[str, Any],
        student_name: str | None = None,
    ) -> Report:
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
