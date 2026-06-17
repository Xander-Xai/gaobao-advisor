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

    # ── Slot extraction ────────────────────────────────────────
    slots: dict
    profile_snapshot: dict
    missing_fields: list[str]

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
    quality_scores: dict           # 4 维度评分
    aggregate_score: float         # 聚合分
    hallucination_flags: list      # 幻觉标记列表
    quality_grade: str             # excellent / pass / fail
