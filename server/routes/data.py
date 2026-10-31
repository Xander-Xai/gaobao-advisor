"""Public read-only admissions data endpoints.

The transport layer validates parameters and delegates SQL to
``server.services.data_catalog``. Existing cursor contracts are preserved;
the explorer adds overview, filter, school-detail and trend resources.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from server.deps import get_db
from server.domain.data_catalog import (
    DataOverviewOut,
    FilterOptionsOut,
    SchoolDetailOut,
    TrendOut,
)
from server.services import data_catalog

router = APIRouter(prefix="/api/v1/data", tags=["data"])

_CURSOR_RE = re.compile(r"[0-9]{1,19}")


def _parse_cursor(cursor: str | None) -> int | None:
    """Validate an opaque cursor before it reaches SQL.

    IDs are positive integers. Malformed/negative values used to raise an
    uncaught ValueError (HTTP 500) or silently compare an integer with a
    string and return an empty page. Both hide the caller's mistake.
    """
    if cursor is None or cursor == "":
        return None
    if not _CURSOR_RE.fullmatch(cursor):
        raise HTTPException(status_code=400, detail="Invalid cursor: expected a non-negative integer")
    value = int(cursor)
    if value < 0 or value > 2**63 - 1:
        raise HTTPException(status_code=400, detail="Invalid cursor: out of range")
    return value


@router.get("/overview", response_model=DataOverviewOut)
def get_overview(db: Session = Depends(get_db)):
    """Data coverage, provenance, and per-year record counts."""
    return data_catalog.get_overview(db)


@router.get("/filters", response_model=FilterOptionsOut)
def get_filters(db: Session = Depends(get_db)):
    """Filter values actually present in the current database."""
    return data_catalog.get_filter_options(db)


@router.get("/schools")
def get_schools(
    school_name: str | None = Query(None, description="学校名称关键词（兼容旧接口）"),
    q: str | None = Query(None, max_length=64, description="院校或城市关键词"),
    province: str | None = Query(None, description="省份"),
    level: str | None = Query(None, description="学校层次"),
    school_type: str | None = Query(None, description="学校类型"),
    limit: int = Query(20, ge=1, le=200, description="每页数量"),
    cursor: str | None = Query(None, description="游标（上一页的 next_cursor）"),
    db: Session = Depends(get_db),
):
    """Search schools by name, province, level or type with cursor pagination."""
    cursor_id = _parse_cursor(cursor)
    if school_name:
        legacy = data_catalog.list_schools(
            db,
            q=school_name,
            province=province,
            level=level,
            school_type=school_type,
            limit=1,
        )
        return {"count": len(legacy["items"]), "results": legacy["items"]}
    return data_catalog.list_schools(
        db,
        q=q,
        province=province,
        level=level,
        school_type=school_type,
        limit=limit,
        cursor=cursor_id,
    )


@router.get("/schools/{school_id}", response_model=SchoolDetailOut)
def get_school_detail(school_id: int, db: Session = Depends(get_db)):
    """One school with bounded score and plan samples plus availability flags."""
    detail = data_catalog.get_school_detail(db, school_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="School not found")
    return detail


@router.get("/scores")
def get_scores(
    school_name: str = Query(..., description="学校名称"),
    province: str = Query(..., description="省份"),
    year: int | None = Query(None, description="年份"),
    major: str | None = Query(None, description="专业"),
    limit: int = Query(50, ge=1, le=200, description="每页数量"),
    cursor: str | None = Query(None, description="游标（上一页的 next_cursor）"),
    db: Session = Depends(get_db),
):
    """Query admission scores for a school with cursor-based pagination."""
    cursor_id = _parse_cursor(cursor)
    return data_catalog.search_scores(
        db,
        school_name=school_name,
        province=province,
        year=year,
        major=major,
        limit=limit,
        cursor=cursor_id,
    )


@router.get("/plans")
def get_plans(
    school_name: str = Query(..., description="学校名称"),
    province: str | None = Query(None, description="省份"),
    year: int | None = Query(None, description="年份"),
    limit: int = Query(50, ge=1, le=200, description="每页数量"),
    cursor: str | None = Query(None, description="游标（上一页的 next_cursor）"),
    db: Session = Depends(get_db),
):
    """Query enrollment plans for a school with cursor-based pagination."""
    cursor_id = _parse_cursor(cursor)
    return data_catalog.search_plans(
        db,
        school_name=school_name,
        province=province,
        year=year,
        limit=limit,
        cursor=cursor_id,
    )


@router.get("/trends", response_model=TrendOut)
def get_trends(
    school_name: str = Query(..., min_length=1, max_length=100, description="学校名称"),
    province: str = Query(..., min_length=1, max_length=20, description="省份"),
    subject_type: str | None = Query(None, max_length=10, description="科类；不传则按科类分别返回"),
    major: str | None = Query(None, max_length=100, description="专业名称；不传则按院校最低分聚合"),
    years: int = Query(3, ge=1, le=10, description="回看年数"),
    db: Session = Depends(get_db),
):
    """Multi-year score trend, always separated by subject type."""
    trend = data_catalog.get_trend(
        db,
        school_name=school_name,
        province=province,
        subject_type=subject_type,
        major=major,
        years=years,
    )
    if trend is None:
        raise HTTPException(status_code=404, detail="School not found")
    return trend
