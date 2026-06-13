"""Memory update node — persists trace and session data."""
from __future__ import annotations

from typing import Any


def memory_update_node(state: dict[str, Any]) -> dict[str, Any]:
    """Record final trace entry for session persistence.

    In the current implementation this appends a summary trace entry.
    Actual database persistence will be added in a future task.
    """
    trace = list(state.get("trace", []))
    reply = state.get("reply", "")
    structured = state.get("structured_result", {})

    trace.append({
        "node": "memory_update",
        "event": "pipeline_complete",
        "reply_length": len(reply),
        "has_structured": bool(structured),
    })

    return {"trace": trace}
