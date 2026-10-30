"""FastAPI routes for the operations workbench."""

from __future__ import annotations

import hashlib
import logging
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy.orm import Session

from server.admin import repository, service
from server.admin.auth import (
    AdminConfigError,
    AdminPrincipal,
    authenticate,
    client_ip_hash,
    get_admin_config,
    issue_admin_token,
    require_role,
)
from server.admin.errors import AdminError
from server.admin.limits import SlidingWindowLimiter
from server.admin.logging import log_event, log_warning
from server.admin.schemas import (
    AdminLoginRequest,
    AdminTokenOut,
    AdminUserOut,
    AuditPageOut,
    QualityJobCreateOut,
    QualityJobCreateRequest,
    QualityJobDetailOut,
    QualityJobFilters,
    QualityJobOut,
    QualityJobPageOut,
    ReviewRequest,
    SchoolDetailOut,
    SchoolPageOut,
    StatsOut,
    SystemStatusOut,
)
from server.deps import get_db
from server.middleware.request_id import get_request_id

logger = logging.getLogger("server.admin.routes")

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

_login_limiter = SlidingWindowLimiter(limit=8, window_seconds=60)
_job_limiter = SlidingWindowLimiter(limit=20, window_seconds=60)

DbSession = Annotated[Session, Depends(get_db)]


def _auth_config() -> None:
    try:
        config = get_admin_config()
    except AdminConfigError as exc:
        raise AdminError(503, "ADMIN_NOT_CONFIGURED", "管理员认证未正确配置") from exc
    if not config.enabled:
        raise AdminError(503, "ADMIN_NOT_CONFIGURED", "管理员入口未启用：请注入 ADMIN_USERS_JSON 或 ADMIN_USERNAME")  # noqa: E501


def _client_key(request: Request) -> str:
    host = request.client.host if request.client else "unknown"
    return hashlib.sha256(host.encode("utf-8", "ignore")).hexdigest()[:24]


def _require_limit(limiter: SlidingWindowLimiter, key: str, code: str) -> None:
    allowed, retry_after = limiter.check(key)
    if not allowed:
        raise AdminError(429, code, "操作过于频繁，请稍后重试", details={"retry_after_seconds": retry_after})


@router.post("/auth/login", response_model=AdminTokenOut)
def login(payload: AdminLoginRequest, request: Request) -> dict[str, Any]:
    _auth_config()
    _require_limit(_login_limiter, _client_key(request), "LOGIN_RATE_LIMITED")
    principal = authenticate(payload.username, payload.password)
    if principal is None:
        log_warning("admin.login.failed", username=payload.username[:64], ip_hash=client_ip_hash(request))
        raise AdminError(401, "INVALID_CREDENTIALS", "用户名或密码错误")
    token, expires_in = issue_admin_token(principal)
    log_event("admin.login.succeeded", username=principal.username, role=principal.role)
    return {
        "access_token": token,
        "expires_in": expires_in,
        "user": {"username": principal.username, "role": principal.role},
    }


@router.get("/auth/me", response_model=AdminUserOut)
def me(principal: AdminPrincipal = Depends(require_role("viewer"))) -> dict[str, Any]:
    return {"username": principal.username, "role": principal.role}


@router.get("/system/status", response_model=SystemStatusOut)
def system_status(
    db: DbSession,
    principal: AdminPrincipal = Depends(require_role("viewer")),
) -> dict[str, Any]:
    return service.system_status(db)


@router.get("/stats", response_model=StatsOut)
def stats(
    db: DbSession,
    principal: AdminPrincipal = Depends(require_role("viewer")),
) -> dict[str, Any]:
    return service.statistics(db)


@router.get("/schools/filters")
def school_filters(
    db: DbSession,
    principal: AdminPrincipal = Depends(require_role("viewer")),
) -> dict[str, list[str]]:
    return repository.list_filter_options(db)


@router.get("/schools", response_model=SchoolPageOut)
def schools(
    db: DbSession,
    principal: AdminPrincipal = Depends(require_role("viewer")),
    q: str | None = Query(default=None, max_length=64),
    province: str | None = Query(default=None, max_length=20),
    level: str | None = Query(default=None, max_length=20),
    school_type: str | None = Query(default=None, max_length=20),
    has_scores: bool | None = Query(default=None),
    min_ranking: int | None = Query(default=None, ge=1, le=100_000),
    max_ranking: int | None = Query(default=None, ge=1, le=100_000),
    sort: Literal["id", "name", "province", "level", "ranking", "score_count"] = Query(default="id"),
    order: Literal["asc", "desc"] = Query(default="asc"),
    page: int = Query(default=1, ge=1, le=100_000),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    if min_ranking is not None and max_ranking is not None and min_ranking > max_ranking:
        raise AdminError(422, "VALIDATION_ERROR", "min_ranking 不能大于 max_ranking")
    filters = {
        "q": q,
        "province": province,
        "level": level,
        "school_type": school_type,
        "has_scores": has_scores,
        "min_ranking": min_ranking,
        "max_ranking": max_ranking,
    }
    return repository.list_schools(
        db,
        filters={k: v for k, v in filters.items() if v is not None},
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )


@router.get("/schools/{school_id}", response_model=SchoolDetailOut)
def school_detail(
    school_id: int,
    db: DbSession,
    principal: AdminPrincipal = Depends(require_role("viewer")),
) -> dict[str, Any]:
    detail = repository.get_school_detail(db, school_id)
    if detail is None:
        raise AdminError(404, "SCHOOL_NOT_FOUND", "院校不存在")
    return detail


@router.get("/quality/jobs", response_model=QualityJobPageOut)
def quality_jobs(
    db: DbSession,
    principal: AdminPrincipal = Depends(require_role("viewer")),
    status: Literal["PENDING", "RUNNING", "SUCCEEDED", "FAILED"] | None = Query(default=None),
    review_status: Literal["PENDING_REVIEW", "APPROVED", "REJECTED"] | None = Query(default=None),
    page: int = Query(default=1, ge=1, le=100_000),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    return service.list_quality_jobs(
        db,
        status=status,
        review_status=review_status,
        page=page,
        page_size=page_size,
    )


@router.post("/quality/jobs", response_model=QualityJobCreateOut)
def create_quality_job(
    payload: QualityJobCreateRequest,
    request: Request,
    response: Response,
    db: DbSession,
    principal: AdminPrincipal = Depends(require_role("operator")),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> dict[str, Any]:
    _require_limit(_job_limiter, f"{principal.username}:{_client_key(request)}", "JOB_RATE_LIMITED")
    filters: QualityJobFilters = payload.filters
    result = service.create_quality_job(
        db,
        filters=filters.model_dump(exclude_none=True),
        idempotency_key=idempotency_key or "",
        actor=principal.username,
        role=principal.role,
        request_id=get_request_id(),
        ip_hash=client_ip_hash(request),
    )
    job = result["job"]
    if result.get("replayed"):
        response.status_code = 200
    elif job["status"] in ("PENDING", "RUNNING"):
        response.status_code = 202
    else:
        response.status_code = 201
    log_event(
        "admin.quality_job.requested",
        job_id=job["id"],
        status=job["status"],
        queue_state=result.get("queue_state"),
        actor=principal.username,
    )
    return result


@router.get("/quality/jobs/{job_id}", response_model=QualityJobDetailOut)
def quality_job_detail(
    job_id: int,
    db: DbSession,
    principal: AdminPrincipal = Depends(require_role("viewer")),
) -> dict[str, Any]:
    return service.get_quality_job(db, job_id)


@router.post("/quality/jobs/{job_id}/review", response_model=QualityJobOut)
def review_quality_job(
    job_id: int,
    payload: ReviewRequest,
    request: Request,
    db: DbSession,
    principal: AdminPrincipal = Depends(require_role("admin")),
) -> dict[str, Any]:
    result = service.review_quality_job(
        db,
        job_id,
        decision=payload.decision,
        note=payload.note,
        expected_version=payload.expected_version,
        actor=principal.username,
        role=principal.role,
        request_id=get_request_id(),
        ip_hash=client_ip_hash(request),
    )
    log_event(
        "admin.quality_job.reviewed",
        job_id=job_id,
        decision=payload.decision,
        actor=principal.username,
    )
    return result


@router.get("/audit-logs", response_model=AuditPageOut)
def audit_logs(
    db: DbSession,
    principal: AdminPrincipal = Depends(require_role("admin")),
    action: str | None = Query(default=None, max_length=64),
    actor: str | None = Query(default=None, max_length=64),
    page: int = Query(default=1, ge=1, le=100_000),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    return repository.list_audit_logs(db, action=action, actor=actor, page=page, page_size=page_size)
