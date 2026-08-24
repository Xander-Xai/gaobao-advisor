"""AdvisorState — TypedDict defining the full graph state."""

from typing import Literal, TypedDict


class AdvisorState(TypedDict, total=False):
    """State passed through every node in the LangGraph advisor pipeline."""

    # ── Identity & Input ───────────────────────────────────────
    session_id: str
    user_id: str
    input_text: str
    scene: Literal["gaokao", "kaoyan", "career", "general"]

    # ── Conversation history ───────────────────────────────────
    messages: list[dict]

    # ── Slot extraction / profile ──────────────────────────────
    slots: dict
    profile_snapshot: dict
    missing_fields: list[str]
    _query_state: dict

    # ── Quality pipeline ───────────────────────────────────────
    emotion_state: str
    cognitive_model: str
    decision_heuristics: list[str]
    anti_pattern_violations: list[dict]

    # ── Knowledge retrieval ────────────────────────────────────
    rag_chunks: list[dict]
    expert_quotes: list[dict]
    data_query_results: dict
    knowledge_context: str

    # ── Reasoning & Output ────────────────────────────────────
    reasoning: str
    structured_result: dict
    reply: str
    confidence: float

    # ── Traceability ──────────────────────────────────────────
    trace: list[dict]

    # ── Quality Judge (LLM-as-Judge) ──────────────────────────
    quality_scores: dict
    aggregate_score: float
    hallucination_flags: list
    quality_grade: str

    # ── Feedback & Rewrite ────────────────────────────────────
    should_rewrite: bool
    needs_rewrite: bool
    rewrite_attempts: int
