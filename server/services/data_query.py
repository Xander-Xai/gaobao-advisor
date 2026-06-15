"""
Data query service wrapper.

Thin wrapper around gaokao_data that exposes a clean interface
for the server layer. All functions delegate directly to the
existing module-level functions.
"""

from __future__ import annotations

from typing import Any


def query_admission(
    school: str,
    province: str,
    year: int | None = None,
    major: str | None = None,
) -> list[dict[str, Any]]:
    """Query admission data for a school."""
    from gaokao_data import query_admission as _query

    return _query(school, province, year, major)


def query_enrollment_plan(
    school_name: str,
    province: str | None = None,
    year: int | None = None,
) -> list[dict[str, Any]]:
    """Query enrollment plans for a school."""
    from gaokao_data import query_enrollment_plan as _query

    return _query(school_name, province, year)


def query_yi_fen_yi_duan(
    province: str,
    score: int,
    subject_type: str = "物理",
    year: int | None = None,
) -> dict[str, Any] | None:
    """Look up the score-to-rank mapping from the one-score-one-rank table."""
    from gaokao_data import query_yi_fen_yi_duan as _query

    return _query(province, score, subject_type, year)


def query_match_schools_v2(
    score: int,
    province: str,
    subject_type: str,
    strategy: str = "稳",
    year: int | None = None,
) -> list[dict[str, Any]]:
    """Match schools using the rank-based method (chong/wen/bao)."""
    from gaokao_data import query_match_schools_v2 as _query

    return _query(score, province, subject_type, strategy, year)


def query_match_schools(
    score: int,
    province: str,
    subject_type: str,
    strategy: str = "稳",
) -> list[dict[str, Any]]:
    """Match schools using score-based method (legacy)."""
    from gaokao_data import query_match_schools as _query

    return _query(score, province, subject_type, strategy)


def query_schools_by_major(
    major_name: str,
    province: str,
    score: int,
    subject_type: str = "物理",
    year: int | None = None,
) -> dict[str, Any]:
    """Reverse-lookup schools that offer a given major."""
    from gaokao_data import query_schools_by_major as _query

    return _query(major_name, province, score, subject_type, year)


def query_school_info(school_name: str) -> dict[str, Any] | None:
    """Get basic info for a school."""
    from gaokao_data import query_school_info as _query

    return _query(school_name)


def query_major_info(major_name: str) -> dict[str, Any] | None:
    """Get employment/salary data for a major."""
    from gaokao_data import query_major_info as _query

    return _query(major_name)


def query_subject_ranking(
    school_name: str,
    category: str | None = None,
) -> list[dict[str, Any]]:
    """Query subject rankings for a school."""
    from gaokao_data import query_subject_ranking as _query

    return _query(school_name, category)


def search_policy(keyword: str) -> list[dict[str, Any]]:
    """Search the built-in policy database."""
    from gaokao_data import search_policy as _query

    return _query(keyword)


def get_db_stats() -> dict[str, Any]:
    """Get database statistics."""
    from gaokao_data import get_db_stats as _query

    return _query()


def check_user_subject_compatibility(
    user_subjects: list[str],
    major_name: str | None = None,
) -> dict[str, Any]:
    """Check whether user's subject choices are compatible with a major."""
    from gaokao_data import check_user_subject_compatibility as _query

    return _query(user_subjects, major_name)


def generate_volunteer_table(
    score: int,
    province: str,
    subject_type: str = "物理",
    year: int | None = None,
    chong_count: int = 2,
    wen_count: int = 5,
    bao_count: int = 3,
) -> dict[str, Any]:
    """Generate a structured volunteer table."""
    from gaokao_data import generate_volunteer_table as _query

    return _query(score, province, subject_type, year, chong_count, wen_count, bao_count)


def query_admission_trend(
    school_name: str,
    province: str,
    subject_type: str,
    years: int = 3,
) -> dict[str, Any] | None:
    """Query multi-year admission trend for a school."""
    from gaokao_data import query_admission_trend as _query

    return _query(school_name, province, subject_type, years)
