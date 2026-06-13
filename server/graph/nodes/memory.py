"""Memory update node -- persists conversation to database."""
from __future__ import annotations

from typing import Any

from db.database import get_session
from db.crud import get_or_create_conversation, save_message, save_slots


def memory_update_node(state: dict[str, Any]) -> dict[str, Any]:
    """Persist conversation data to the database."""
    session_id = state.get("session_id", "")
    slots = state.get("slots", {})
    input_text = state.get("input_text", "")
    reply = state.get("reply", "")

    if not session_id:
        trace = list(state.get("trace", []))
        trace.append({"node": "memory_update", "event": "skipped_no_session_id"})
        return {"trace": trace}

    try:
        db = next(get_session())
        get_or_create_conversation(db, session_id)
        if input_text:
            save_message(db, session_id, "user", input_text)
        if reply:
            save_message(db, session_id, "assistant", reply)
        save_slots(db, session_id, slots)
    except Exception:
        pass  # Don't let persistence failure block the pipeline

    trace = list(state.get("trace", []))
    trace.append({"node": "memory_update", "event": "persisted"})
    return {"trace": trace}
