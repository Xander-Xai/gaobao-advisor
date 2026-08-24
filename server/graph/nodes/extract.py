"""Slot extraction node — parses user text into structured slots."""

from __future__ import annotations

import re
from typing import Any

from slots.extractor import SlotExtractor

_extractor = SlotExtractor()


def _parse_score_rank(value: Any) -> tuple[int | None, int | None]:
    """Parse the extractor's score/rank text into canonical numeric fields.

    The extractor intentionally keeps a human-readable ``score_rank`` value for
    backwards compatibility (for example ``600分 / 位次25000``). Downstream
    business logic should use the canonical ``score`` and ``rank`` fields.
    """
    if value is None:
        return None, None

    text = str(value)
    score: int | None = None
    rank: int | None = None

    score_match = re.search(r"(\d{2,3})\s*分", text)
    if score_match:
        candidate = int(score_match.group(1))
        if 100 <= candidate <= 750:
            score = candidate

    rank_match = re.search(r"(?:位次|排名)\s*[:：]?\s*(\d[\d,]*)", text)
    if rank_match:
        candidate = int(rank_match.group(1).replace(",", ""))
        if candidate > 0:
            rank = candidate

    return score, rank


def slot_extract_node(state: dict[str, Any]) -> dict[str, Any]:
    """Extract structured slots from user input text.

    Newly extracted values are merged with the existing session slots. The
    graph keeps ``score_rank`` for compatibility while also exposing canonical
    numeric ``score`` / ``rank`` fields so data queries and rendering use one
    stable contract.
    """
    text = state.get("input_text", "")
    existing = state.get("slots", {}) or {}

    new_slots_dict, _updated = _extractor.extract(text)

    merged: dict[str, Any] = {}
    for key, slot in new_slots_dict.items():
        if slot.get("filled"):
            merged[key] = slot["value"]

    # Existing non-empty values win, preserving information collected in
    # previous turns.
    for key, value in existing.items():
        if value not in (None, "", [], {}):
            merged[key] = value

    # Normalize score/rank after merge so it also works for persisted sessions.
    raw_score_rank = merged.get("score_rank")
    parsed_score, parsed_rank = _parse_score_rank(raw_score_rank)

    if merged.get("score") in (None, "") and parsed_score is not None:
        merged["score"] = parsed_score
    elif isinstance(merged.get("score"), str) and merged["score"].isdigit():
        merged["score"] = int(merged["score"])

    if merged.get("rank") in (None, "") and parsed_rank is not None:
        merged["rank"] = parsed_rank
    elif isinstance(merged.get("rank"), str) and merged["rank"].replace(",", "").isdigit():
        merged["rank"] = int(merged["rank"].replace(",", ""))

    trace = list(state.get("trace", []))
    trace.append(
        {
            "node": "slot_extract",
            "event": "slots_merged",
            "count": len([value for value in merged.values() if value not in (None, "", [], {})]),
        }
    )
    return {"slots": merged, "trace": trace}
