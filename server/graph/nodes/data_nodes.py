"""Data query node — fetches admission and school data."""

from __future__ import annotations

import re
from typing import Any

from config.loader import load_tuning
from server.services import data_query as dq

_DEFAULT_STRATEGY = load_tuning().get("data_query", {}).get("default_strategy", "稳")


def _extract_score(val: Any) -> int | None:
    """Extract integer score from a slot value (string with optional 分 suffix, or sub-dict)."""
    if isinstance(val, dict):
        val = val.get("value", "")
    if val is None:
        return None
    raw = str(val).strip()
    # Strip "分" suffix if present
    raw = re.sub(r"分$", "", raw)
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


def _normalize_subject(val: Any) -> str | None:
    """Normalize subject slot value for data query."""
    if isinstance(val, dict):
        val = val.get("value", "")
    return val


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
            province = _normalize_subject(slots.get("province"))
            raw_score = _extract_score(slots.get("score_rank") or slots.get("score"))
            subject = _normalize_subject(slots.get("subject"))
            interest = _normalize_subject(slots.get("interest"))

            if province and raw_score and subject:
                # Normalize subject for query
                subject_type = (
                    "物理" if subject in ("理科", "物理") else "历史" if subject in ("文科", "历史") else subject
                )

                # Match schools
                results["match_schools"] = dq.query_match_schools_v2(
                    score=raw_score,
                    province=province,
                    subject_type=subject_type,
                    strategy=_DEFAULT_STRATEGY,
                )

                # One-score-one-rank
                yfyd = dq.query_yi_fen_yi_duan(province, raw_score, subject_type)
                if yfyd:
                    results["rank_info"] = yfyd

            # School by major
            if interest and province and raw_score:
                subject_type = (
                    "物理" if subject in ("理科", "物理") else "历史" if subject in ("文科", "历史") else "物理"
                )
                results["schools_by_major"] = dq.query_schools_by_major(
                    major_name=interest,
                    province=province,
                    score=raw_score,
                    subject_type=subject_type,
                )

            # Major info
            if interest:
                major_info = dq.query_major_info(interest)
                if major_info:
                    results["major_info"] = major_info

        elif scene == "kaoyan":
            interest = _normalize_subject(slots.get("interest"))
            if interest:
                major_info = dq.query_major_info(interest)
                if major_info:
                    results["major_info"] = major_info

    except Exception as exc:
        results["error"] = str(exc)

    trace = list(state.get("trace", []))
    trace.append(
        {
            "node": "data_query",
            "event": f"keys={list(results.keys())}",
        }
    )

    return {"data_query_results": results, "trace": trace}
