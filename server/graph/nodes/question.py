"""Question generation node — soul query style + static fallback.

Generates a follow-up question when the user's profile is incomplete.
Uses the SoulQueryEngine for intelligent, conversational questions and
falls back to the static question bank if the engine is unavailable.

The soul query engine is preferred because it:
- Only asks about genuinely missing fields
- Cycles through multiple question variants
- Stops after MAX_QUERY_ROUNDS even if incomplete
- Supports skip/default values for optional fields
"""

from __future__ import annotations

from typing import Any

from server.soul_query import OPTIONAL_QUESTIONS, REQUIRED_QUESTIONS, QueryState, SoulQueryEngine
from server.user_profile import load_profile

# Static question bank (fallback when soul query is not available)
QUESTION_BANK: dict[str, dict[str, str]] = {
    "gaokao": {
        "province": "请问您是哪个省的考生呢？",
        "score_rank": "请问您的高考分数是多少分？",
        "subject": "请问您是文科还是理科？或者新高考选科组合是什么？",
        "interest": "请问您对哪些专业方向比较感兴趣呢？",
        "region": "您对学校所在地区有什么偏好吗？",
        "family": "能简单介绍一下您的家庭背景吗？",
        "goal": "您未来有什么规划呢？比如考研、出国、就业还是考公？",
    },
    "kaoyan": {
        "interest": "请问您想考哪个专业方向的研究生呢？",
        "goal": "请问您的目标院校是哪里？或者对学校层次有什么要求？",
    },
    "career": {
        "interest": "请问您对哪些职业方向比较感兴趣？",
    },
    "general": {},
}


def question_generate_node(state: dict[str, Any]) -> dict[str, Any]:
    """Generate a follow-up question using soul query or static bank.

    Priority:
    1. SoulQueryEngine (if session_id is available and profile can be loaded)
    2. Static QUESTION_BANK (fallback based on scene and missing_fields)
    3. Generic "what else" question (if nothing matches)
    """
    session_id = state.get("session_id", "")
    scene = state.get("scene", "general")
    missing = state.get("missing_fields", [])

    # Try soul query first
    if session_id:
        try:
            profile = load_profile(session_id)
            if profile and not profile.is_required_complete():
                engine = SoulQueryEngine()
                query_state = _load_query_state(state)
                question = engine.get_next_question(profile, query_state)
                if question:
                    _save_query_state_into_state(state, query_state)
                    trace = list(state.get("trace", []))
                    trace.append(
                        {
                            "node": "question_generate",
                            "event": "soul_question",
                            "field": _find_target_field(question, engine),
                            "round": query_state.round_count,
                        }
                    )
                    return {"reply": question, "trace": trace}
        except Exception:
            pass  # Fall through to static bank

    # Static fallback
    bank = QUESTION_BANK.get(scene, QUESTION_BANK["general"])
    questions = []
    for field in missing:
        q = bank.get(field)
        if q:
            questions.append(q)

    if not questions:
        questions.append("请问还有什么我可以帮您了解的吗？")

    reply = "\n".join(questions)

    trace = list(state.get("trace", []))
    trace.append(
        {
            "node": "question_generate",
            "event": "static_fallback",
            "questions_asked": len(questions),
        }
    )
    return {"reply": reply, "trace": trace}


def _load_query_state(state: dict[str, Any]) -> QueryState:
    """Load QueryState from state dict (per-session tracking)."""
    qs = state.get("_query_state", {})
    return QueryState(
        round_count=qs.get("round_count", 0),
        asked_fields=qs.get("asked_fields", []),
        skipped_fields=qs.get("skipped_fields", []),
    )


def _save_query_state_into_state(state: dict[str, Any], qs: QueryState) -> None:
    """Save QueryState back into the state dict."""
    state["_query_state"] = {
        "round_count": qs.round_count,
        "asked_fields": qs.asked_fields,
        "skipped_fields": qs.skipped_fields,
    }


def _find_target_field(question: str, engine: SoulQueryEngine) -> str | None:
    """Guess which field the question targets."""
    for field_name in ["province", "score", "subject", "interest", "region", "family", "goal"]:
        variants = REQUIRED_QUESTIONS.get(field_name, []) + OPTIONAL_QUESTIONS.get(field_name, [])
        for variant in variants:
            if question.startswith(variant[:10]):
                return field_name
    return None
