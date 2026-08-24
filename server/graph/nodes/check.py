"""Profile check node — identifies missing required fields."""

from __future__ import annotations

from typing import Any

from server.graph.nodes.extract import _parse_score_rank
from server.graph.nodes.route import SCENE_CONFIGS


def _slot_filled(slots: dict[str, Any], field: str) -> bool:
    """Return whether a required field is satisfied by the canonical slot contract."""
    if field == "score_rank":
        if slots.get("score"):
            return True
        score_rank = slots.get("score_rank")
        if score_rank:
            score, _rank = _parse_score_rank(score_rank)
            return score is not None
        return False
    return bool(slots.get(field))


def profile_check_node(state: dict[str, Any]) -> dict[str, Any]:
    """Check whether all required slots for the scene are filled."""
    scene = state.get("scene", "general")
    slots = state.get("slots", {}) or {}
    config = SCENE_CONFIGS.get(scene, SCENE_CONFIGS["general"])
    required = config["required_slots"]

    missing = [field for field in required if not _slot_filled(slots, field)]
    profile = {key: value for key, value in slots.items() if value}

    trace = list(state.get("trace", []))
    trace.append(
        {
            "node": "profile_check",
            "event": f"missing={len(missing)}",
            "missing_fields": missing,
        }
    )

    return {
        "missing_fields": missing,
        "profile_snapshot": profile,
        "trace": trace,
    }
