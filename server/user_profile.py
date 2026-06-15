"""User Profile — structured model for student information.

Adapted from zhangxuefeng-agent's user_profile.py (backend/user_profile.py:27-100).
Replaces Redis persistence with SQLite to match gaobao-advisor's architecture.

This profile model represents what we know about the user. Fields align with
the 7 slots from slots/extractor.py and are used by SoulQueryEngine to decide
what to ask next.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class UserProfile:
    """Student/user profile with required and optional fields.

    Required fields (gate questions — must collect before giving advice):
    - province: 省份
    - score: 高考分数 (int)
    - subject: 选科 (文/理 or 3+1+2/3+3 combination)
    - interest: 专业意向

    Optional fields (nice-to-have):
    - region: 地域偏好
    - family: 家庭背景
    - goal: 核心诉求 (考研/就业/考公/出国)
    """

    REQUIRED_FIELDS = {"province", "score", "subject", "interest"}

    def __init__(self) -> None:
        self.province: str | None = None
        self.score: int | None = None
        self.subject: str | None = None
        self.interest: str | None = None
        # Optional
        self.region: str | None = None
        self.family: str | None = None
        self.goal: str | None = None

    @classmethod
    def from_slots(cls, slots: dict) -> UserProfile:
        """Create a profile from the slot extractor's output format.

        Slot format: {"province": {"value": "山东", "filled": True}, ...}
        """
        profile = cls()
        field_map = {
            "province": "province",
            "score_rank": "score",
            "subject": "subject",
            "interest": "interest",
            "region": "region",
            "family": "family",
            "goal": "goal",
        }
        for slot_key, profile_key in field_map.items():
            slot = slots.get(slot_key, {})
            if slot.get("filled") and slot.get("value"):
                value = slot["value"]
                # Extract numeric score from strings like "580分"
                # but NOT from "位次3000" (which contains a rank number, not a score)
                if profile_key == "score":
                    import re

                    # Only parse if the value explicitly contains "分"
                    if "分" in str(value):
                        m = re.search(r"(\d{2,3})", str(value))
                        if m:
                            score = int(m.group(1))
                            if 100 <= score <= 750:
                                setattr(profile, profile_key, score)
                else:
                    setattr(profile, profile_key, str(value))
        return profile

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for storage/API."""
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
        """Deserialize from dict."""
        profile = cls()
        for key in ("province", "score", "subject", "interest", "region", "family", "goal"):
            val = data.get(key)
            if val is not None:
                setattr(profile, key, val)
        return profile

    def is_required_complete(self) -> bool:
        """All required fields are filled."""
        return all(
            [
                self.province is not None,
                self.score is not None,
                self.subject is not None,
                self.interest is not None,
            ]
        )

    def missing_required_fields(self) -> list[str]:
        """Return list of missing required field names."""
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
        """Count how many fields (required + optional) are filled."""
        return sum(
            1
            for f in ("province", "score", "subject", "interest", "region", "family", "goal")
            if getattr(self, f) is not None
        )

    def to_context_dict(self) -> dict[str, str]:
        """Export as context dict for LLM prompt injection."""
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


# ── Load/save profile from DB conversation slots ──────────────────


def load_profile(session_id: str) -> UserProfile:
    """Load profile from the database (stored as conversation slots).

    If no profile exists, returns an empty UserProfile.
    """
    from db.crud import load_conversation_slots
    from db.database import get_session

    db = get_session()
    try:
        slot_data = load_conversation_slots(db, session_id)
        if slot_data:
            return UserProfile.from_slots(slot_data)
    except Exception:
        logger.warning("Failed to load profile for session %s", session_id)
    finally:
        db.close()

    return UserProfile()


def save_profile(session_id: str, profile: UserProfile) -> None:
    """Save profile by extracting filled fields."""
    from db.crud import get_or_create_conversation, save_slots
    from db.database import get_session

    db = get_session()
    try:
        get_or_create_conversation(db, session_id)
        # Extract slots from profile fields
        slots = {}
        if profile.province:
            slots["province"] = {"value": profile.province, "filled": True}
        if profile.score is not None:
            slots["score_rank"] = {"value": f"{profile.score}分", "filled": True}
        if profile.subject:
            slots["subject"] = {"value": profile.subject, "filled": True}
        if profile.interest:
            slots["interest"] = {"value": profile.interest, "filled": True}
        if profile.region:
            slots["region"] = {"value": profile.region, "filled": True}
        if profile.family:
            slots["family"] = {"value": profile.family, "filled": True}
        if profile.goal:
            slots["goal"] = {"value": profile.goal, "filled": True}

        save_slots(db, session_id, slots)
    except Exception:
        logger.warning("Failed to save profile for session %s", session_id)
    finally:
        db.close()
