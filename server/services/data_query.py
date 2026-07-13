"""
Data query service wrapper.

Thin wrapper around gaokao_data that exposes a clean interface
for the server layer. All functions delegate directly to the
existing module-level functions.
"""

from __future__ import annotations

from typing import Any

from config.loader import load_tuning

_DEFAULT_SUBJECT = load_tuning().get("data_query", {}).get("default_subject_type", "物理")
_NUMERIC_EVIDENCE_KEYS = {
    "min_score",
    "avg_score",
    "max_score",
    "min_rank",
    "rank",
    "plan_count",
    "employment_rate",
    "avg_salary",
}


def annotate_provenance(value: Any) -> Any:
    """Copy query results and make provenance gaps machine-readable."""
    if isinstance(value, list):
        return [annotate_provenance(item) for item in value]
    if not isinstance(value, dict):
        return value

    annotated = {key: annotate_provenance(item) for key, item in value.items()}
    if not (_NUMERIC_EVIDENCE_KEYS & annotated.keys()):
        return annotated

    source = annotated.get("data_source") or annotated.get("source") or annotated.get("data_source_note")
    source_text = str(source or "")
    synthetic = bool(annotated.get("synthetic")) or "synthetic demo" in source_text.lower() or "合成演示" in source_text
    if synthetic:
        annotated.update(
            synthetic=True,
            provenance_status="synthetic",
            data_source="合成演示数据，不可用于真实志愿决策",
            confidence_score=0,
        )
    elif not source or not annotated.get("year"):
        annotated.update(
            provenance_status="unverified",
            data_source="无法验证来源或年份，请以省考试院和高校官网为准",
            confidence_score=min(annotated.get("confidence_score", 20), 20),
        )
    else:
        annotated.setdefault("provenance_status", "declared")
    return annotated


def query_admission(
    school: str,
    province: str,
    year: int | None = None,
    major: str | None = None,
) -> list[dict[str, Any]]:
    """Query admission data for a school."""
    from legacy.gaokao_data import query_admission as _query

    return annotate_provenance(_query(school, province, year, major))


def query_enrollment_plan(
    school_name: str,
    province: str | None = None,
    year: int | None = None,
) -> list[dict[str, Any]]:
    """Query enrollment plans for a school."""
    from legacy.gaokao_data import query_enrollment_plan as _query

    return annotate_provenance(_query(school_name, province, year))


def query_yi_fen_yi_duan(
    province: str,
    score: int,
    subject_type: str = _DEFAULT_SUBJECT,
    year: int | None = None,
) -> dict[str, Any] | None:
    """Look up the score-to-rank mapping from the one-score-one-rank table."""
    from legacy.gaokao_data import query_yi_fen_yi_duan as _query

    return annotate_provenance(_query(province, score, subject_type, year))


def query_match_schools_v2(
    score: int,
    province: str,
    subject_type: str,
    strategy: str = "稳",
    year: int | None = None,
) -> list[dict[str, Any]]:
    """Match schools using the rank-based method (chong/wen/bao)."""
    from legacy.gaokao_data import query_match_schools_v2 as _query

    return annotate_provenance(_query(score, province, subject_type, strategy, year))


def query_match_schools(
    score: int,
    province: str,
    subject_type: str,
    strategy: str = "稳",
) -> list[dict[str, Any]]:
    """Match schools using score-based method (legacy)."""
    from legacy.gaokao_data import query_match_schools as _query

    return annotate_provenance(_query(score, province, subject_type, strategy))


def query_schools_by_major(
    major_name: str,
    province: str,
    score: int,
    subject_type: str = _DEFAULT_SUBJECT,
    year: int | None = None,
) -> dict[str, Any]:
    """Reverse-lookup schools that offer a given major."""
    from legacy.gaokao_data import query_schools_by_major as _query

    return annotate_provenance(_query(major_name, province, score, subject_type, year))


def query_school_info(school_name: str) -> dict[str, Any] | None:
    """Get basic info for a school."""
    from legacy.gaokao_data import query_school_info as _query

    return _query(school_name)


def query_major_info(major_name: str) -> dict[str, Any] | None:
    """Get employment/salary data for a major."""
    from legacy.gaokao_data import query_major_info as _query

    return annotate_provenance(_query(major_name))


def query_subject_ranking(
    school_name: str,
    category: str | None = None,
) -> list[dict[str, Any]]:
    """Query subject rankings for a school."""
    from legacy.gaokao_data import query_subject_ranking as _query

    return annotate_provenance(_query(school_name, category))


def search_policy(keyword: str) -> list[dict[str, Any]]:
    """Search the built-in policy database."""
    from legacy.gaokao_data import search_policy as _query

    return _query(keyword)


def get_db_stats() -> dict[str, Any]:
    """Get database statistics."""
    from legacy.gaokao_data import get_db_stats as _query

    return _query()


def check_user_subject_compatibility(
    user_subjects: list[str],
    major_name: str | None = None,
) -> dict[str, Any]:
    """Check whether user's subject choices are compatible with a major."""
    from legacy.gaokao_data import check_user_subject_compatibility as _query

    return _query(user_subjects, major_name)


def generate_volunteer_table(
    score: int,
    province: str,
    subject_type: str = _DEFAULT_SUBJECT,
    year: int | None = None,
    chong_count: int = 2,
    wen_count: int = 5,
    bao_count: int = 3,
) -> dict[str, Any]:
    """Generate a structured volunteer table."""
    from legacy.gaokao_data import generate_volunteer_table as _query

    return annotate_provenance(_query(score, province, subject_type, year, chong_count, wen_count, bao_count))


def query_admission_trend(
    school_name: str,
    province: str,
    subject_type: str,
    years: int = 3,
) -> dict[str, Any] | None:
    """Query multi-year admission trend for a school."""
    from legacy.gaokao_data import query_admission_trend as _query

    return annotate_provenance(_query(school_name, province, subject_type, years))
