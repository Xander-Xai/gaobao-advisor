"""Profile check node — identifies missing required fields."""

from __future__ import annotations

from typing import Any

from server.graph.nodes.route import SCENE_CONFIGS


def profile_check_node(state: dict[str, Any]) -> dict[str, Any]:
    """Check whether all required slots for the scene are filled.

    Sets missing_fields to any required slot that is missing or falsy.
    Also builds a profile_snapshot from filled slots.
    """
    scene = state.get("scene", "general")
    slots = state.get("slots", {})
    config = SCENE_CONFIGS.get(scene, SCENE_CONFIGS["general"])
    required = config["required_slots"]

    def _has_required(field: str) -> bool:
        if field == "score_rank":
            return bool(slots.get("score_rank") or slots.get("score"))
        return bool(slots.get(field))

    missing = [field for field in required if not _has_required(field)]

    # Build profile snapshot from filled slots
    profile = {k: v for k, v in slots.items() if v}

    trace = list(state.get("trace", []))
    trace.append(
        {
            "node": "profile_check",
            "event": f"missing={len(missing)}",
            "missing_fields": missing,
        }
    )

    result: dict[str, Any] = {
        "missing_fields": missing,
        "profile_snapshot": profile,
        "trace": trace,
    }
    return result
