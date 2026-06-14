"""Soul Query Engine — intelligent question-asking for user profiling.

Adapted from zhangxuefeng-agent's soul_query.py (backend/soul_query.py:1-143).

Strategy:
1. Check required fields (province, score, subject, interest) — if any are
   missing, generate a natural follow-up question.
2. After required fields are complete, optionally ask about nice-to-have
   fields (region, family, goal).
3. Maximum 5 rounds of questioning to avoid annoying the user.
4. Questions are designed to feel conversational ("灵魂追问"), not like a form.

Calling convention:
    engine = SoulQueryEngine()
    question = engine.get_next_question(profile, query_state)
    if question:
        # Ask the user
    else:
        # Profile is complete — proceed with advice
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from server.user_profile import UserProfile

logger = logging.getLogger(__name__)

# Maximum rounds of questioning before we stop (even if not complete)
MAX_QUERY_ROUNDS = 5

# ── Required field questions (asked first, in priority order) ──────
REQUIRED_QUESTIONS: dict[str, list[str]] = {
    "province": [
        "请问您是哪个省的考生？这个很关键，不同省份分数线天差地别。",
        "您的省份我还没记下，是哪个省的高考生？",
        "您是哪个省份的？我得先知道这个才能帮您分析。",
    ],
    "score": [
        "您考了多少分？分数是选学校的核心依据。",
        "方便告诉一下高考分数吗？有了分数才能做精准推荐。",
        "孩子高考多少分？这个信息最重要。",
    ],
    "subject": [
        "您是文科还是理科？新高考的话选的哪几科？",
        "选科情况说一下，文理分科还是新高考选科组合？",
        "文科/理科/新高考选科是什么？这个直接影响专业选择范围。",
    ],
    "interest": [
        "有没有特别想学的专业方向？或者有没有什么职业理想？",
        "对什么专业方向比较感兴趣？计算机、医学、法律还是其他？",
        "想学什么方向？或者有没有特别不想学的专业？",
    ],
}

# ── Optional field questions (asked after required are complete) ───
OPTIONAL_QUESTIONS: dict[str, list[str]] = {
    "region": [
        "有没有特别想去的城市或地区？",
        "将来想留在哪个城市发展？还是想出去闯闯？",
    ],
    "family": [
        "家里什么条件？这个会影响选校选专业的策略。",
        "方便说一下家庭情况吗？工薪家庭还是做生意，策略不一样。",
    ],
    "goal": [
        "未来有什么规划？考研、就业、考公还是出国？",
        "孩子以后打算考研继续深造，还是想直接就业？",
    ],
}

# Default values when user skips an optional question
SKIP_DEFAULTS: dict[str, str] = {
    "region": "不限",
    "family": "参考",
    "goal": "未确定",
}

# Ordered list of all fields for the question queue
_REQUIRED_ORDER = ["province", "score", "subject", "interest"]
_OPTIONAL_ORDER = ["region", "family", "goal"]


@dataclass
class QueryState:
    """Tracks the state of questioning."""

    round_count: int = 0
    asked_fields: list[str] = field(default_factory=list)
    skipped_fields: list[str] = field(default_factory=list)


class SoulQueryEngine:
    """Intelligent question-asking for user profiling.

    Usage:
        engine = SoulQueryEngine()
        state = QueryState()
        question = engine.get_next_question(profile, state)
        if question:
            yield question  # stream to user
        else:
            yield profile.to_context_dict()  # proceed with advice
    """

    def get_next_question(self, profile: UserProfile, state: QueryState) -> str | None:
        """Get the next question to ask the user.

        Returns:
            Question string, or None if all required info is collected.
        """
        if state.round_count >= MAX_QUERY_ROUNDS:
            logger.info("Reached max query rounds (%d), stopping", MAX_QUERY_ROUNDS)
            return None

        # Phase 1: Required fields
        for field_name in _REQUIRED_ORDER:
            if getattr(profile, field_name, None) is None:
                if field_name not in state.asked_fields:
                    question = self._pick_question(field_name, state.round_count)
                    state.asked_fields.append(field_name)
                    state.round_count += 1
                    return question

        # Phase 2: Optional fields (one per round after required are done)
        for field_name in _OPTIONAL_ORDER:
            val = getattr(profile, field_name, None)
            if val is None and field_name not in state.asked_fields and field_name not in state.skipped_fields:
                question = self._pick_optional_question(field_name)
                state.asked_fields.append(field_name)
                state.round_count += 1
                return question

        return None

    def handle_skip(self, state: QueryState, field_name: str) -> None:
        """User skipped a question — record it and apply default value."""
        if field_name not in state.skipped_fields:
            state.skipped_fields.append(field_name)
            logger.info("User skipped field: %s", field_name)

    def is_query_complete(self, profile: UserProfile) -> bool:
        """Check if required info is complete."""
        return profile.is_required_complete()

    def get_skip_default(self, field_name: str) -> str | None:
        """Get the default value for a skipped optional field."""
        return SKIP_DEFAULTS.get(field_name)

    def apply_skip_defaults(self, profile: UserProfile, state: QueryState) -> None:
        """Apply default values for skipped optional fields."""
        for field_name in state.skipped_fields:
            default = SKIP_DEFAULTS.get(field_name)
            if default and getattr(profile, field_name, None) is None:
                setattr(profile, field_name, default)
                logger.info("Applied default '%s' for skipped field '%s'", default, field_name)

    def _pick_question(self, field_name: str, round_count: int) -> str:
        """Pick a question for a required field, cycling through variants."""
        questions = REQUIRED_QUESTIONS.get(field_name, [f"请告诉我您的{field_name}"])
        idx = round_count % len(questions) if questions else 0
        return questions[idx] if questions else f"请告诉我您的{field_name}"

    def _pick_optional_question(self, field_name: str) -> str:
        """Pick a question for an optional field."""
        questions = OPTIONAL_QUESTIONS.get(field_name, [f"方便的话告诉我您的{field_name}"])
        return questions[0] if questions else f"方便的话告诉我您的{field_name}"
