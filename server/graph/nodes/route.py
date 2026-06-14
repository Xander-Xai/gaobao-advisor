"""Scene routing node — configures required slots per scene."""
from __future__ import annotations

from typing import Any

# Required slot keys for each scene
SCENE_CONFIGS: dict[str, dict[str, list[str]]] = {
    "gaokao": {
        "required_slots": ["province", "score_rank", "subject", "interest"],
    },
    "kaoyan": {
        "required_slots": ["interest", "goal"],
    },
    "career": {
        "required_slots": ["interest"],
    },
    "general": {
        "required_slots": [],
    },
}


def scene_route_node(state: dict[str, Any]) -> dict[str, Any]:
    """Attach scene-specific configuration to the trace.

    This node does not modify slots — it records which scene config is active
    so downstream nodes (profile_check, question_generate) can reference it.
    """
    scene = state.get("scene", "general")
    config = SCENE_CONFIGS.get(scene, SCENE_CONFIGS["general"])

    trace = list(state.get("trace", []))
    trace.append({
        "node": "scene_route",
        "event": f"scene={scene}",
        "required_slots": config["required_slots"],
    })
    return {"trace": trace}
