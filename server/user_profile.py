"""User Profile — structured model for student information.

Adapted from zhangxuefeng-agent's user_profile.py (backend/user_profile.py:27-100).
Replaces Redis persistence with SQLite to match gaobao-advisor's architecture.

This profile model represents what we know about the user. Fields align with
the 7 slots from slots/extractor.py and are used by SoulQueryEngine to decide
what to ask next.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class UserProfile:
    """Student/user profile with required and optional fields."""

    REQUIRED_FIELDS = {"province", "score", "subject", "interest"}

    def __init__(self) -> None:
        self.province: str | None = None
        self.score: int | None = None
        self.subject: str | None = None
        self.interest: str | None = None
        self.region: str | None = None
        self.family: str | None = None
        self.goal: str | None = None

    @staticmethod
    def _slot_value(slots: dict, key: str) -> Any:
        """Read either legacy nested slots or the graph's flat slot format."""
        raw = slots.get(key)
        if isinstance(raw, dict):
            if not raw.get("filled"):
                return None
            return raw.get("value")
        return raw

    @staticmethod
    def _parse_score(value: Any) -> int | None:
        if isinstance(value, int):
            return value if 100 <= value <= 750 else None
        if value is None:
            return None
        text = str(value)
        match = re.search(r"(\d{2,3})\s*分", text)
        if not match and text.strip().isdigit():
            match = re.search(r"(\d{2,3})", text)
        if match:
            score = int(match.group(1))
            if 100 <= score <= 750:
                return score
        return None

    @classmethod
    def from_slots(cls, slots: dict) -> UserProfile:
        """Create a profile from either nested or flat persisted slots."""
        profile = cls()

        profile.province = cls._slot_value(slots, "province") or None
        profile.subject = cls._slot_value(slots, "subject") or None
        profile.interest = cls._slot_value(slots, "interest") or None
        profile.region = cls._slot_value(slots, "region") or None
        profile.family = cls._slot_value(slots, "family") or None
        profile.goal = cls._slot_value(slots, "goal") or None

        # Prefer the canonical score field. Fall back to legacy score_rank.
        profile.score = cls._parse_score(cls._slot_value(slots, "score"))
        if profile.score is None:
            profile.score = cls._parse_score(cls._slot_value(slots, "score_rank"))

        for key in ("province", "subject", "interest", "region", "family", "goal"):
            value = getattr(profile, key)
            if value is not None:
                setattr(profile, key, str(value))
        return profile

    def to_dict(self) -> dict[str, Any]:
        return {
            "province": self.province,
            "score": self.score,
            "subject": self.subject,
            "interest": self.interest,
            "region": self.region,
            "family": self.family,
            "goal": self.goal,
        }

    @classmethod
    def from_dict(cls, data: dict) -> UserProfile:
        profile = cls()
        for key in ("province", "score", "subject", "interest", "region", "family", "goal"):
            val = data.get(key)
            if val is not None:
                setattr(profile, key, val)
        return profile

    def is_required_complete(self) -> bool:
        return all(
            [
                self.province is not None,
                self.score is not None,
                self.subject is not None,
                self.interest is not None,
            ]
        )

    def missing_required_fields(self) -> list[str]:
        missing = []
        if self.province is None:
            missing.append("province")
        if self.score is None:
            missing.append("score")
        if self.subject is None:
            missing.append("subject")
        if self.interest is None:
            missing.append("interest")
        return missing

    def count_filled(self) -> int:
        return sum(
            1
            for field in ("province", "score", "subject", "interest", "region", "family", "goal")
            if getattr(self, field) is not None
        )

    def to_context_dict(self) -> dict[str, str]:
        ctx = {}
        if self.province:
            ctx["省份"] = self.province
        if self.score is not None:
            ctx["分数"] = str(self.score)
        if self.subject:
            ctx["选科"] = self.subject
        if self.interest:
            ctx["专业意向"] = self.interest
        if self.region:
            ctx["地域偏好"] = self.region
        if self.family:
            ctx["家庭背景"] = self.family
        if self.goal:
            ctx["核心诉求"] = self.goal
        return ctx


def load_profile(session_id: str) -> UserProfile:
    """Load profile from the database (stored as conversation slots)."""
    from db.crud import load_conversation_slots
    from db.database import get_session

    db = get_session()
    try:
        slot_data = load_conversation_slots(db, session_id)
        if slot_data:
            return UserProfile.from_slots(slot_data)
    except Exception:
        logger.warning("Failed to load profile for session %s", session_id, exc_info=True)
    finally:
        db.close()

    return UserProfile()


def save_profile(session_id: str, profile: UserProfile) -> None:
    """Merge profile fields into the session's flat slot representation."""
    from db.crud import get_or_create_conversation, load_conversation_slots, save_slots
    from db.database import get_session

    db = get_session()
    try:
        get_or_create_conversation(db, session_id)
        slots = load_conversation_slots(db, session_id) or {}

        if profile.province:
            slots["province"] = profile.province
        if profile.score is not None:
            slots["score"] = profile.score
            slots["score_rank"] = f"{profile.score}分"
        if profile.subject:
            slots["subject"] = profile.subject
        if profile.interest:
            slots["interest"] = profile.interest
        if profile.region:
            slots["region"] = profile.region
        if profile.family:
            slots["family"] = profile.family
        if profile.goal:
            slots["goal"] = profile.goal

        save_slots(db, session_id, slots)
    except Exception:
        logger.warning("Failed to save profile for session %s", session_id, exc_info=True)
    finally:
        db.close()
