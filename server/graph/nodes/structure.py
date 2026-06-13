"""Structure output node — builds a structured planning card."""
from __future__ import annotations

from typing import Any


def structure_output_node(state: dict[str, Any]) -> dict[str, Any]:
    """Build a structured result dict (planning card) from gathered data.

    This produces the JSON payload that the frontend can render as
    a rich card with school recommendations, score analysis, etc.
    """
    scene = state.get("scene", "general")
    slots = state.get("slots", {})
    data = state.get("data_query_results", {})
    reasoning = state.get("reasoning", "")

    structured: dict[str, Any] = {
        "scene": scene,
        "profile": {k: v for k, v in slots.items() if v},
    }

    if scene == "gaokao":
        match_schools = data.get("match_schools", [])
        if match_schools:
            # Build school cards
            schools = []
            for s in match_schools[:10]:
                schools.append({
                    "name": s.get("school_name", s.get("name", "")),
                    "score_line": s.get("score_line", s.get("min_score", "")),
                    "province": s.get("province", ""),
                    "category": s.get("category", ""),
                })
            structured["matched_schools"] = schools

        rank_info = data.get("rank_info")
        if rank_info:
            structured["rank_analysis"] = rank_info

        major_info = data.get("major_info")
        if major_info:
            structured["major_analysis"] = major_info

        schools_by_major = data.get("schools_by_major", {})
        if schools_by_major:
            structured["schools_by_major"] = schools_by_major

    elif scene == "kaoyan":
        major_info = data.get("major_info")
        if major_info:
            structured["major_analysis"] = major_info

    # Include confidence estimate
    filled_count = len([v for v in slots.values() if v])
    total_slots = len(slots) if slots else 7
    structured["confidence"] = round(filled_count / max(total_slots, 1), 2)

    trace = list(state.get("trace", []))
    trace.append({"node": "structure_output", "event": "card_built"})

    return {"structured_result": structured, "trace": trace}
