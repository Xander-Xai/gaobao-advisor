"""Slot extraction node — parses user text into structured slots."""
from __future__ import annotations

from typing import Any

from server.services.slot_extractor import SlotExtractor

_extractor = SlotExtractor()


def slot_extract_node(state: dict[str, Any]) -> dict[str, Any]:
    """Extract structured slots from user input text.

    Merges newly extracted slots with any existing slots (existing wins
    for keys that already have a truthy value).
    """
    text = state.get("input_text", "")
    existing = state.get("slots", {})

    new_slots = _extractor.extract(text)

    # Merge: keep existing truthy values, fill in from new
    merged = {
        **{k: v for k, v in new_slots.items() if v},
        **{k: v for k, v in existing.items() if v},
    }

    trace = list(state.get("trace", []))
    trace.append({"node": "slot_extract", "event": f"slots_merged", "count": len([v for v in merged.values() if v])})
    return {"slots": merged, "trace": trace}
