"""Memory node — persists conversation to database."""
from __future__ import annotations

import logging
from typing import Any

from db.database import get_session
from db.crud import get_or_create_conversation, save_message, save_slots

logger = logging.getLogger(__name__)


def memory_node(state: dict[str, Any]) -> dict[str, Any]:
    """Persist conversation data to the database."""
    session_id = state.get("session_id", "")
    slots = state.get("slots", {})
    input_text = state.get("input_text", "")
    reply = state.get("reply", "")

    trace = list(state.get("trace", []))

    if not session_id:
        trace.append({"node": "memory_update", "event": "skipped_no_session_id"})
        return {"trace": trace}

    db = get_session()
    try:
        get_or_create_conversation(db, session_id)
        if input_text:
            save_message(db, session_id, "user", input_text)
        if reply:
            save_message(db, session_id, "assistant", reply)
        save_slots(db, session_id, slots)
        trace.append({"node": "memory_update", "event": "persisted"})
    except Exception as exc:
        logger.warning("memory_update failed: %s", exc)
        trace.append({"node": "memory_update", "event": "persist_failed", "error": str(exc)[:200]})
    finally:
        db.close()

    return {"trace": trace}
