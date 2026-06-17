"""Report data model for gaokao advisory reports."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Report:
    """Structured gaokao advisory report.

    Generated from conversation data via StructuredPlanningCard.
    Stored as JSON files in data/reports/{session_id}/.
    """

    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    # Student info
    student_name: str | None = None
    province: str = ""
    score: int = 0
    subject: str = ""
    interest: str = ""

    # Structured content (from StructuredPlanningCard)
    summary: str = ""
    facts: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    confidence: float = 0.0

    # Metadata
    match_schools: list[dict] = field(default_factory=list)
    scene: str = "gaokao"

    @classmethod
    def from_slots(cls, session_id: str, slots: dict[str, Any]) -> Report:
        """Create a Report from slot extractor output.

        Slot format: {"province": {"value": "山东", "filled": True}, ...}
        """
        def _get_slot(key: str) -> str:
            val = slots.get(key, {})
            if isinstance(val, dict):
                return str(val.get("value", ""))
            return str(val) if val else ""

        def _get_int(key: str) -> int:
            val = _get_slot(key)
            try:
                return int(str(val).replace("分", ""))
            except (ValueError, TypeError):
                return 0

        return cls(
            session_id=session_id,
            student_name=_get_slot("name") or None,
            province=_get_slot("province"),
            score=_get_int("score"),
            subject=_get_slot("subject"),
            interest=_get_slot("interest"),
            summary=f"{_get_slot('province')}，{_get_slot('score')}分，意向{_get_slot('interest')}，规划分析中。",
            scene="gaokao",
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON storage."""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Report:
        """Deserialize from dict."""
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
