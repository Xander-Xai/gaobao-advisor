"""Slot extraction node — parses user text into structured slots."""

from __future__ import annotations

from typing import Any

from server.graph.nodes.data_nodes import numeric_score
from slots.extractor import SlotExtractor

_extractor = SlotExtractor()


def slot_extract_node(state: dict[str, Any]) -> dict[str, Any]:
    """Extract structured slots from user input text.

    Newly extracted slots fill gaps. Existing truthy values win by default so
    a passing mention ("北京校区怎么样") cannot silently replace a collected
    profile. Explicit corrections ("我改成620分") and a newly stated interest
    are the exception: they override the old value.
    """
    text = state.get("input_text", "")
    existing = state.get("slots", {})

    # slots.extractor.SlotExtractor.extract() returns (slots_dict, updated_list)
    new_slots_dict, _updated = _extractor.extract(text)
    override_fields = _extractor.detect_override_fields(text)

    merged = {}
    for k, v in new_slots_dict.items():
        if v.get("filled"):
            merged[k] = v["value"]
    for k, v in existing.items():
        if v:
            merged[k] = v
    for key in override_fields:
        slot = new_slots_dict.get(key)
        if slot and slot.get("filled"):
            merged[key] = slot["value"]

    # Downstream nodes (data query, render, structured card) need a numeric
    # score, while the extractor stores the user-facing "600分" in score_rank.
    # Recompute it after an override; otherwise a corrected score would keep
    # the stale integer next to the new score_rank string.
    if "score_rank" in override_fields:
        merged.pop("score", None)
    score = numeric_score({"score_rank": merged.get("score_rank")})
    if score is None:
        score = numeric_score(merged)
    if score is not None:
        merged["score"] = score

    trace = list(state.get("trace", []))
    trace.append(
        {
            "node": "slot_extract",
            "event": "slots_merged",
            "count": len([v for v in merged.values() if v]),
            "overrides": sorted(override_fields),
        }
    )
    return {"slots": merged, "trace": trace}
