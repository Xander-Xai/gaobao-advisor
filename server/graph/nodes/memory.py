"""Memory node — persists conversation to database.

Upgraded from bare persistence to dual-layer memory management:
1. Recent N rounds preserved verbatim (in the DB conversation history).
2. Older rounds can be summarized via LLM for long-running conversations.
"""

from __future__ import annotations

import logging
from typing import Any

from db.crud import get_or_create_conversation, save_message, save_slots
from db.database import get_session
from server.agent.llm_reliability import estimate_messages_tokens

logger = logging.getLogger(__name__)

SUMMARIZE_AFTER_ROUNDS = 15


def memory_node(state: dict[str, Any]) -> dict[str, Any]:
    """Persist conversation data, slots, and per-session query state."""
    session_id = state.get("session_id", "")
    slots = dict(state.get("slots", {}) or {})
    query_state = state.get("_query_state")
    if query_state:
        slots["_query_state"] = query_state

    input_text = state.get("input_text", "")
    reply = state.get("reply", "")
    trace = list(state.get("trace", []))

    if not session_id:
        trace.append({"node": "memory_update", "event": "skipped_no_session_id"})
        return {"trace": trace}

    db = get_session()
    try:
        conv = get_or_create_conversation(db, session_id)
        if input_text:
            save_message(db, session_id, "user", input_text)
        if reply:
            save_message(db, session_id, "assistant", reply)
        save_slots(db, session_id, slots)

        msg_count = len(conv.messages) if conv.id else 0
        needs_summary = msg_count > SUMMARIZE_AFTER_ROUNDS * 2
        estimated_tokens = estimate_messages_tokens([{"content": m.content} for m in (conv.messages or [])])

        trace.append(
            {
                "node": "memory_update",
                "event": "persisted",
                "msg_count": msg_count,
                "estimated_tokens": estimated_tokens,
                "needs_summary": needs_summary,
            }
        )
    except Exception as exc:
        logger.warning("memory_update failed: %s", exc)
        trace.append(
            {
                "node": "memory_update",
                "event": "persist_failed",
                "error": str(exc)[:200],
            }
        )
    finally:
        db.close()

    return {"trace": trace}
