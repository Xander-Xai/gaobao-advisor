"""Data query endpoints with cursor-based pagination."""

from fastapi import APIRouter, Query

from db.pagination import paginate_cursor
from server.services.data_query import (
    query_school_info,
)

router = APIRouter(prefix="/api/v1/data", tags=["data"])


@router.get("/schools")
async def get_schools(
    school_name: str | None = Query(None, description="学校名称关键词"),
    province: str | None = Query(None, description="省份"),
    level: str | None = Query(None, description="学校层次"),
    limit: int = Query(50, ge=1, le=200, description="每页数量"),
    cursor: str | None = Query(None, description="游标（上一页的 next_cursor）"),
):
    """Search schools by name, province, or level with cursor-based pagination."""
    from db.database import SessionLocal
    from db.models import School

    session = SessionLocal()
    try:
        # Build filters
        filters = {}
        if province:
            filters["province"] = province
        if level:
            filters["level"] = level

        # For school_name search, use full-text search instead of pagination
        if school_name:
            result = query_school_info(school_name)
            results = [result] if result else []
            return {"count": len(results), "results": results}

        # Use cursor-based pagination for listing
        page_result = paginate_cursor(
            session,
            School,
            order_by=School.id,
            limit=limit,
            cursor=cursor,
            filters=filters if filters else None,
        )

        return {
            "items": [school.__dict__ for school in page_result.items],
            "next_cursor": page_result.next_cursor,
            "has_more": page_result.has_more,
        }
    finally:
        session.close()


@router.get("/scores")
async def get_scores(
    school_name: str = Query(..., description="学校名称"),
    province: str = Query(..., description="省份"),
    year: int | None = Query(None, description="年份"),
    major: str | None = Query(None, description="专业"),
    limit: int = Query(50, ge=1, le=200, description="每页数量"),
    cursor: str | None = Query(None, description="游标（上一页的 next_cursor）"),
):
    """Query admission scores for a school with cursor-based pagination."""
    from sqlalchemy import and_

    from db.database import SessionLocal
    from db.models import AdmissionScore, School

    session = SessionLocal()
    try:
        # Find school by name
        school = session.query(School).filter(School.name == school_name).first()
        if not school:
            return {"items": [], "next_cursor": None, "has_more": False}

        # Build query
        query = session.query(AdmissionScore).filter(
            and_(
                AdmissionScore.school_id == school.id,
                AdmissionScore.province == province,
            )
        )

        if year:
            query = query.filter(AdmissionScore.year == year)
        if major:
            query = query.filter(AdmissionScore.major == major)

        # Apply cursor
        if cursor:
            query = query.filter(AdmissionScore.id > int(cursor))

        # Order and limit
        query = query.order_by(AdmissionScore.id).limit(limit + 1)
        items = query.all()

        # Check has_more
        has_more = len(items) > limit
        if has_more:
            items = items[:limit]

        # Next cursor
        next_cursor = str(items[-1].id) if items and has_more else None

        # Convert to dict with school/major names
        results = []
        for item in items:
            result = {
                "id": item.id,
                "school_name": school_name,
                "province": item.province,
                "year": item.year,
                "batch": item.batch,
                "subject_type": item.subject_type,
                "min_score": item.min_score,
                "avg_score": item.avg_score,
                "max_score": item.max_score,
                "min_rank": item.min_rank,
            }
            if item.major:
                result["major"] = item.major.name
            results.append(result)

        return {
            "items": results,
            "next_cursor": next_cursor,
            "has_more": has_more,
        }
    finally:
        session.close()


@router.get("/plans")
async def get_plans(
    school_name: str = Query(..., description="学校名称"),
    province: str | None = Query(None, description="省份"),
    year: int | None = Query(None, description="年份"),
    limit: int = Query(50, ge=1, le=200, description="每页数量"),
    cursor: str | None = Query(None, description="游标（上一页的 next_cursor）"),
):
    """Query enrollment plans for a school with cursor-based pagination."""

    from db.database import SessionLocal
    from db.models import EnrollmentPlan, School

    session = SessionLocal()
    try:
        # Find school by name
        school = session.query(School).filter(School.name == school_name).first()
        if not school:
            return {"items": [], "next_cursor": None, "has_more": False}

        # Build query
        query = session.query(EnrollmentPlan).filter(
            EnrollmentPlan.school_id == school.id
        )

        if province:
            query = query.filter(EnrollmentPlan.province == province)
        if year:
            query = query.filter(EnrollmentPlan.year == year)

        # Apply cursor
        if cursor:
            query = query.filter(EnrollmentPlan.id > int(cursor))

        # Order and limit
        query = query.order_by(EnrollmentPlan.id).limit(limit + 1)
        items = query.all()

        # Check has_more
        has_more = len(items) > limit
        if has_more:
            items = items[:limit]

        # Next cursor
        next_cursor = str(items[-1].id) if items and has_more else None

        # Convert to dict with school/major names
        results = []
        for item in items:
            result = {
                "id": item.id,
                "school_name": school_name,
                "province": item.province,
                "year": item.year,
                "plan_count": item.plan_count,
                "subject_requirement": item.subject_requirement,
                "batch": item.batch,
                "duration": item.duration,
                "tuition": item.tuition,
            }
            if item.major:
                result["major"] = item.major.name
            results.append(result)

        return {
            "items": results,
            "next_cursor": next_cursor,
            "has_more": has_more,
        }
    finally:
        session.close()
