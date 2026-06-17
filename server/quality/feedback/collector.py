"""Feedback collector — explicit user feedback and implicit signal detection."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from db.crud import save_feedback
from db.database import SessionLocal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExplicitFeedback:
    """A single piece of explicit user feedback on an AI reply."""

    conversation_id: str
    message_index: int
    rating: str  # "helpful" / "not_helpful"
    feedback_text: Optional[str] = None
    quality_score_id: Optional[int] = None
    source: str = "explicit"


@dataclass(frozen=True)
class ImplicitSignal:
    """An implicit signal detected from user behaviour."""

    conversation_id: str
    signal_type: str
    description: str
    confidence: float


class FeedbackCollector:
    """Collects explicit feedback and detects implicit signals."""

    def save_feedback(
        self,
        conversation_id: str,
        message_index: int,
        rating: str,
        feedback_text: str | None = None,
        quality_score_id: int | None = None,
    ) -> bool:
        """Persist user feedback to the database.

        Uses the existing ``save_feedback`` CRUD function for the core
        upsert logic, then updates the extra columns (feedback_text,
        quality_score_id) that the CRUD function does not cover.

        Returns True on success, False on failure.
        """
        try:
            with SessionLocal() as db:
                ok = save_feedback(db, conversation_id, message_index, rating)
                if not ok:
                    return False

                # Update optional columns on the upserted row
                from db.models import Feedback

                row = (
                    db.query(Feedback)
                    .filter(
                        Feedback.session_id == conversation_id,
                        Feedback.message_index == message_index,
                    )
                    .first()
                )
                if row is not None:
                    if feedback_text is not None:
                        row.feedback_text = feedback_text
                    if quality_score_id is not None:
                        row.quality_score_id = quality_score_id
                    db.commit()

                return True
        except Exception:
            logger.exception(
                "Failed to save feedback for session=%s index=%d",
                conversation_id,
                message_index,
            )
            return False

    def detect_implicit_signals(
        self,
        conversation_id: str,
        messages: list[dict],
    ) -> list[ImplicitSignal]:
        """Detect implicit negative/positive signals from conversation.

        Placeholder for future implicit signal detection.
        Currently returns an empty list.
        """
        # Future: analyse rephrasing, follow-up corrections, session
        # abandonment, etc.  For now this is a no-op.
        return []
