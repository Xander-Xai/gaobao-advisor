"""Graph node for LLM-as-Judge quality evaluation."""

import hashlib
import json
import logging

from quality.judge import QualityJudge

logger = logging.getLogger(__name__)


def _stable_message_id(reply: str) -> str:
    """Generate a deterministic message_id from reply content.

    Uses hashlib.md5 (stable across runs) instead of Python's hash()
    which changes per process due to PYTHONHASHSEED randomization.
    """
    return hashlib.md5(reply.encode("utf-8")).hexdigest()[:16]


def quality_judge_node(state: dict) -> dict:
    """Evaluate AI reply quality using LLM judge."""
    reply = state.get("reply", "")
    query = state.get("input_text", "")
    if not reply or not query:
        return {}

    judge = QualityJudge()
    context = {
        "knowledge_chunks": [
            c.get("text", "") for c in state.get("rag_chunks", []) if isinstance(c, dict) and "text" in c
        ],
        "conversation_history": state.get("messages", []),
        "slots": state.get("slots", {}),
    }

    result = judge.evaluate_sync(query, reply, context)

    # Record Prometheus metrics
    try:
        from server.metrics import record_hallucination, record_judge_score

        for dim, score in result.scores.items():
            record_judge_score(dim, score)
        for flag in result.hallucination_flags:
            flag_type = flag.split(":")[0] if ":" in flag else "unknown"
            record_hallucination(flag_type)
    except Exception:
        logger.warning("Failed to record judge metrics", exc_info=True)

    # Persist to DB
    try:
        from db.database import SessionLocal
        from db.models import QualityScore

        with SessionLocal() as session:
            qs = QualityScore(
                conversation_id=state.get("session_id", ""),
                message_id=_stable_message_id(reply),
                factual_score=result.scores.get("factual"),
                relevance_score=result.scores.get("relevance"),
                helpfulness_score=result.scores.get("helpfulness"),
                style_score=result.scores.get("style"),
                aggregate_score=result.aggregate_score,
                hallucination_flags=json.dumps(result.hallucination_flags),
                judge_model=result.judge_model,
                judge_latency_ms=result.latency_ms,
            )
            session.add(qs)
            session.commit()
    except Exception:
        logger.warning("Failed to persist quality score to DB", exc_info=True)

    return {
        "quality_scores": result.scores,
        "aggregate_score": result.aggregate_score,
        "hallucination_flags": result.hallucination_flags,
        "quality_grade": result.grade,
    }
