"""Data query node — fetches admission and school data."""
from __future__ import annotations

from typing import Any

from server.services import data_query as dq


def data_query_node(state: dict[str, Any]) -> dict[str, Any]:
    """Query relevant admission data based on filled slots.

    For the gaokao scene, queries matching schools and score data.
    Handles errors gracefully — data query failures should not block the pipeline.
    """
    scene = state.get("scene", "general")
    slots = state.get("slots", {})
    results: dict[str, Any] = {}

    try:
        if scene == "gaokao":
            province = slots.get("province")
            score = slots.get("score")
            subject = slots.get("subject")
            interest = slots.get("interest")

            if province and score and subject:
                # Normalize subject for query
                subject_type = "物理" if subject in ("理科", "物理") else "历史" if subject in ("文科", "历史") else subject

                # Match schools
                results["match_schools"] = dq.query_match_schools_v2(
                    score=score,
                    province=province,
                    subject_type=subject_type,
                    strategy="稳",
                )

                # One-score-one-rank
                yfyd = dq.query_yi_fen_yi_duan(province, score, subject_type)
                if yfyd:
                    results["rank_info"] = yfyd

            # School by major
            if interest and province and score:
                subject_type = "物理" if subject in ("理科", "物理") else "历史" if subject in ("文科", "历史") else "物理"
                results["schools_by_major"] = dq.query_schools_by_major(
                    major_name=interest,
                    province=province,
                    score=score,
                    subject_type=subject_type,
                )

            # Major info
            if interest:
                major_info = dq.query_major_info(interest)
                if major_info:
                    results["major_info"] = major_info

        elif scene == "kaoyan":
            interest = slots.get("interest")
            if interest:
                major_info = dq.query_major_info(interest)
                if major_info:
                    results["major_info"] = major_info

    except Exception as exc:
        results["error"] = str(exc)

    trace = list(state.get("trace", []))
    trace.append({
        "node": "data_query",
        "event": f"keys={list(results.keys())}",
    })

    return {"data_query_results": results, "trace": trace}
