"""Data query endpoints."""

from fastapi import APIRouter, Query

from server.services.data_query import (
    query_admission,
    query_enrollment_plan,
    query_school_info,
)

router = APIRouter(prefix="/api/v1/data", tags=["data"])


@router.get("/schools")
async def get_schools(
    school_name: str | None = Query(None, description="学校名称关键词"),
    province: str | None = Query(None, description="省份"),
    level: str | None = Query(None, description="学校层次"),
):
    """Search schools by name, province, or level."""
    if school_name:
        result = query_school_info(school_name)
        results = [result] if result else []
    else:
        results = []
    return {"count": len(results), "results": results[:50]}


@router.get("/scores")
async def get_scores(
    school_name: str = Query(..., description="学校名称"),
    province: str = Query(..., description="省份"),
    year: int | None = Query(None, description="年份"),
    major: str | None = Query(None, description="专业"),
):
    """Query admission scores for a school."""
    results = query_admission(school_name, province=province, year=year, major=major)
    return {"count": len(results), "results": results[:100]}


@router.get("/plans")
async def get_plans(
    school_name: str = Query(..., description="学校名称"),
    province: str | None = Query(None, description="省份"),
    year: int | None = Query(None, description="年份"),
):
    """Query enrollment plans for a school."""
    results = query_enrollment_plan(school_name=school_name, province=province, year=year)
    return {"count": len(results), "results": results[:100]}
