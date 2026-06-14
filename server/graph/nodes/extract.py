"""Slot extraction node — parses user text into structured slots."""
from __future__ import annotations

from typing import Any

from slots.extractor import SlotExtractor

_extractor = SlotExtractor()


def slot_extract_node(state: dict[str, Any]) -> dict[str, Any]:
    """Extract structured slots from user input text.

    Merges newly extracted slots with any existing slots (existing wins
    for keys that already have a truthy value).
    """
    text = state.get("input_text", "")
    existing = state.get("slots", {})

    # slots.extractor.SlotExtractor.extract() returns (slots_dict, updated_list)
    new_slots_dict, _updated = _extractor.extract(text)

    # Merge: keep existing truthy values, fill in from new
    merged = {}
    for k, v in new_slots_dict.items():
        if v.get("filled"):
            merged[k] = v["value"]
    for k, v in existing.items():
        if v:
            merged[k] = v

    trace = list(state.get("trace", []))
    trace.append({"node": "slot_extract", "event": "slots_merged", "count": len([v for v in merged.values() if v])})
    return {"slots": merged, "trace": trace}
