"""Data access layer for the operations workbench.

Routes and services never build SQL directly. Everything that touches the
database lives here, which keeps transactions, pagination and dialect
compatibility testable in isolation.
"""

from __future__ import annotations

import datetime
import json
import math
from collections.abc import Iterable
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from db.models import (
    AdmissionScore,
    DataQualityIssue,
    DataQualityJob,
    EnrollmentPlan,
    Major,
    OperationAuditLog,
    QualityTaskOutbox,
    School,
)
from server.admin.errors import AdminError
from server.admin.privacy import sanitize_detail

JOB_STATUSES = ("PENDING", "RUNNING", "SUCCEEDED", "FAILED")
SEVERITIES = ("ERROR", "WARNING", "INFO")
SORT_COLUMNS = {
    "id": School.id,
    "name": School.name,
    "province": School.province,
    "level": School.level,
    "ranking": School.ranking,
}


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _safe_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _pages(total: int, page_size: int) -> int:
    return math.ceil(total / page_size) if total else 0


def _school_stats_subqueries():
    score_count = (
        select(func.count(AdmissionScore.id))
        .where(AdmissionScore.school_id == School.id)
        .correlate(School)
        .scalar_subquery()
    )
    plan_count = (
        select(func.count(EnrollmentPlan.id))
        .where(EnrollmentPlan.school_id == School.id)
        .correlate(School)
        .scalar_subquery()
    )
    latest_year = (
        select(func.max(AdmissionScore.year))
        .where(AdmissionScore.school_id == School.id)
        .correlate(School)
        .scalar_subquery()
    )
    latest_min = (
        select(func.min(AdmissionScore.min_score))
        .where(
            AdmissionScore.school_id == School.id,
            AdmissionScore.year == latest_year,
        )
        .correlate(School)
        .scalar_subquery()
    )
    return score_count, plan_count, latest_year, latest_min


def _school_query(filters: dict[str, Any]):
    score_count, plan_count, latest_year, latest_min = _school_stats_subqueries()
    query = select(
        School.id,
        School.name,
        School.province,
        School.city,
        School.level,
        School.school_type,
        School.ranking,
        School.is_985,
        School.is_211,
        School.is_double_first_class,
        School.special_type,
        School.data_source_note,
        score_count.label("score_count"),
        plan_count.label("plan_count"),
        latest_year.label("latest_year"),
        latest_min.label("latest_min_score"),
    )
    if filters.get("q"):
        like = f"%{_escape_like(str(filters['q']))}%"
        query = query.where(or_(School.name.like(like, escape="\\"), School.city.like(like, escape="\\")))
    if filters.get("province"):
        query = query.where(School.province == filters["province"])
    if filters.get("level"):
        query = query.where(School.level == filters["level"])
    if filters.get("school_type"):
        query = query.where(School.school_type == filters["school_type"])
    if filters.get("min_ranking") is not None:
        query = query.where(School.ranking >= int(filters["min_ranking"]))
    if filters.get("max_ranking") is not None:
        query = query.where(School.ranking <= int(filters["max_ranking"]))
    if filters.get("school_id") is not None:
        query = query.where(School.id == int(filters["school_id"]))
    if filters.get("has_scores"):
        score_count_sq = (
            select(func.count(AdmissionScore.id))
            .where(AdmissionScore.school_id == School.id)
            .correlate(School)
            .scalar_subquery()
        )
        query = query.where(score_count_sq > 0)
    return query


def _school_count_query(filters: dict[str, Any]):
    query = select(func.count(School.id))
    if filters.get("q"):
        like = f"%{_escape_like(str(filters['q']))}%"
        query = query.where(or_(School.name.like(like, escape="\\"), School.city.like(like, escape="\\")))
    if filters.get("province"):
        query = query.where(School.province == filters["province"])
    if filters.get("level"):
        query = query.where(School.level == filters["level"])
    if filters.get("school_type"):
        query = query.where(School.school_type == filters["school_type"])
    if filters.get("min_ranking") is not None:
        query = query.where(School.ranking >= int(filters["min_ranking"]))
    if filters.get("max_ranking") is not None:
        query = query.where(School.ranking <= int(filters["max_ranking"]))
    if filters.get("school_id") is not None:
        query = query.where(School.id == int(filters["school_id"]))
    if filters.get("has_scores"):
        query = query.where(
            select(func.count(AdmissionScore.id))
            .where(AdmissionScore.school_id == School.id)
            .correlate(School)
            .scalar_subquery()
            > 0
        )
    return query


def list_schools(
    session: Session,
    *,
    filters: dict[str, Any],
    sort: str,
    order: str,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    total = int(session.execute(_school_count_query(filters)).scalar_one())
    query = _school_query(filters)
    if sort == "score_count":
        # score_count is a labelled subquery column; reuse the same expression.
        score_count = _school_stats_subqueries()[0]
        sort_column = score_count
    else:
        sort_column = SORT_COLUMNS.get(sort, School.id)
    sort_column = sort_column.desc() if order == "desc" else sort_column.asc()
    offset = (page - 1) * page_size
    query = query.order_by(sort_column, School.id.asc()).offset(offset).limit(page_size)
    rows = [dict(row._mapping) for row in session.execute(query).all()]
    return {
        "items": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": _pages(total, page_size),
    }


def get_school_detail(session: Session, school_id: int) -> dict[str, Any] | None:
    base = list_schools(
        session,
        filters={"school_id": school_id},
        sort="id",
        order="asc",
        page=1,
        page_size=1,
    )
    if not base["items"]:
        return None
    item = base["items"][0]
    school = session.get(School, school_id)
    if school is None:
        return None
    scores = (
        session.query(AdmissionScore)
        .options(joinedload(AdmissionScore.major))
        .filter(AdmissionScore.school_id == school_id)
        .order_by(AdmissionScore.year.desc(), AdmissionScore.min_score.asc())
        .limit(100)
        .all()
    )
    plans = (
        session.query(EnrollmentPlan)
        .options(joinedload(EnrollmentPlan.major))
        .filter(EnrollmentPlan.school_id == school_id)
        .order_by(EnrollmentPlan.year.desc(), EnrollmentPlan.id.asc())
        .limit(100)
        .all()
    )
    item.update(
        {
            "website": school.website,
            "description": school.description,
            "scores": [
                {
                    "id": row.id,
                    "major_name": row.major.name if row.major else None,
                    "province": row.province,
                    "year": row.year,
                    "batch": row.batch,
                    "subject_type": row.subject_type,
                    "min_score": row.min_score,
                    "avg_score": row.avg_score,
                    "max_score": row.max_score,
                    "min_rank": row.min_rank,
                    "plan_count": row.plan_count,
                }
                for row in scores
            ],
            "plans": [
                {
                    "id": row.id,
                    "major_name": row.major.name if row.major else None,
                    "province": row.province,
                    "year": row.year,
                    "plan_count": row.plan_count,
                    "subject_requirement": row.subject_requirement,
                    "batch": row.batch,
                    "tuition": row.tuition,
                }
                for row in plans
            ],
        }
    )
    return item


def list_filter_options(session: Session) -> dict[str, list[str]]:
    def _distinct(column) -> list[str]:
        rows = session.execute(select(column).where(column.is_not(None)).distinct().order_by(column)).scalars().all()
        return [str(row) for row in rows if row]

    return {
        "provinces": _distinct(School.province),
        "levels": _distinct(School.level),
        "school_types": _distinct(School.school_type),
    }


def get_stats(session: Session) -> dict[str, Any]:
    jobs_by_status = {status: 0 for status in JOB_STATUSES}
    for status, count in session.query(DataQualityJob.status, func.count(DataQualityJob.id)).group_by(
        DataQualityJob.status
    ):
        jobs_by_status[str(status)] = int(count)

    issues_by_severity = {severity: 0 for severity in SEVERITIES}
    for severity, count in session.query(DataQualityIssue.severity, func.count(DataQualityIssue.id)).group_by(
        DataQualityIssue.severity
    ):
        issues_by_severity[str(severity)] = int(count)

    schools_by_level: dict[str, int] = {}
    for level, count in session.query(School.level, func.count(School.id)).group_by(School.level):
        schools_by_level[str(level)] = int(count)

    from server.services.data_profile import detect_data_profile

    return {
        "data_profile": detect_data_profile(session),
        "schools": int(session.query(func.count(School.id)).scalar() or 0),
        "majors": int(session.query(func.count(Major.id)).scalar() or 0),
        "admission_scores": int(session.query(func.count(AdmissionScore.id)).scalar() or 0),
        "enrollment_plans": int(session.query(func.count(EnrollmentPlan.id)).scalar() or 0),
        "jobs_total": int(session.query(func.count(DataQualityJob.id)).scalar() or 0),
        "jobs_by_status": jobs_by_status,
        "issues_by_severity": issues_by_severity,
        "schools_by_level": schools_by_level,
        "pending_review": int(
            session.query(func.count(DataQualityJob.id))
            .filter(DataQualityJob.review_status == "PENDING_REVIEW", DataQualityJob.status == "SUCCEEDED")
            .scalar()
            or 0
        ),
        "audit_events": int(session.query(func.count(OperationAuditLog.id)).scalar() or 0),
        "last_job_at": session.query(func.max(DataQualityJob.created_at)).scalar(),
    }


def record_audit(
    session: Session,
    *,
    request_id: str,
    actor: str,
    role: str,
    action: str,
    resource_type: str,
    resource_id: str | int = "",
    outcome: str = "SUCCESS",
    detail: dict[str, Any] | None = None,
    ip_hash: str | None = None,
) -> OperationAuditLog:
    row = OperationAuditLog(
        request_id=request_id[:64],
        actor=actor[:64],
        role=role[:24],
        action=action[:64],
        resource_type=resource_type[:40],
        resource_id=str(resource_id)[:64],
        outcome=outcome[:16],
        detail_json=json.dumps(sanitize_detail(detail or {}), ensure_ascii=False, default=str),
        ip_hash=ip_hash,
    )
    session.add(row)
    return row


def serialize_job(job: DataQualityJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "review_status": job.review_status,
        "idempotency_key": job.idempotency_key,
        "filters": _safe_json(job.filters_json),
        "requested_by": job.requested_by,
        "execution_mode": job.execution_mode,
        "source_marker": job.source_marker,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "version": job.version,
        "checked_rows": job.checked_rows,
        "issue_count": job.issue_count,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "review_note": job.review_note,
        "reviewed_by": job.reviewed_by,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "reviewed_at": job.reviewed_at,
    }


def serialize_issue(issue: DataQualityIssue) -> dict[str, Any]:
    return {
        "id": issue.id,
        "rule_code": issue.rule_code,
        "severity": issue.severity,
        "entity_type": issue.entity_type,
        "entity_id": issue.entity_id,
        "field_name": issue.field_name,
        "message": issue.message,
        "suggestion": issue.suggestion,
    }


def serialize_audit(row: OperationAuditLog) -> dict[str, Any]:
    return {
        "id": row.id,
        "request_id": row.request_id,
        "actor": row.actor,
        "role": row.role,
        "action": row.action,
        "resource_type": row.resource_type,
        "resource_id": row.resource_id,
        "outcome": row.outcome,
        "detail": _safe_json(row.detail_json),
        "created_at": row.created_at,
    }


def create_job_with_outbox(
    session: Session,
    *,
    filters: dict[str, Any],
    idempotency_key: str,
    actor: str,
    role: str,
    request_id: str,
    ip_hash: str | None,
    max_attempts: int = 3,
) -> tuple[DataQualityJob, bool]:
    canonical_filters = json.dumps(filters, ensure_ascii=False, sort_keys=True)
    existing = session.query(DataQualityJob).filter(DataQualityJob.idempotency_key == idempotency_key).first()
    if existing is not None:
        if existing.filters_json != canonical_filters:
            raise AdminError(
                409,
                "IDEMPOTENCY_CONFLICT",
                "同一 Idempotency-Key 已用于不同的质检范围",
            )
        return existing, True

    job = DataQualityJob(
        status="PENDING",
        review_status="PENDING_REVIEW",
        idempotency_key=idempotency_key,
        filters_json=canonical_filters,
        requested_by=actor,
        execution_mode="pending",
        max_attempts=max_attempts,
    )
    session.add(job)
    try:
        session.flush()
        session.add(
            QualityTaskOutbox(
                job_id=job.id,
                payload_json=json.dumps({"job_id": job.id}, ensure_ascii=False),
                status="PENDING",
            )
        )
        record_audit(
            session,
            request_id=request_id,
            actor=actor,
            role=role,
            action="quality_job.created",
            resource_type="data_quality_job",
            resource_id=job.id,
            detail={"filters": filters, "source_marker": job.source_marker},
            ip_hash=ip_hash,
        )
        session.commit()
    except IntegrityError:
        # Concurrent retry with the same idempotency key: the unique index is
        # the source of truth. Roll everything back and return the winner.
        session.rollback()
        winner = session.query(DataQualityJob).filter(DataQualityJob.idempotency_key == idempotency_key).first()
        if winner is None:
            raise
        return winner, True
    except Exception:
        session.rollback()
        raise
    session.refresh(job)
    return job, False


def get_job(session: Session, job_id: int) -> DataQualityJob | None:
    return session.get(DataQualityJob, job_id)


def get_job_detail(session: Session, job_id: int) -> dict[str, Any] | None:
    job = session.get(DataQualityJob, job_id)
    if job is None:
        return None
    return {
        "job": serialize_job(job),
        "issues": [serialize_issue(issue) for issue in job.issues],
    }


def list_jobs(
    session: Session,
    *,
    status: str | None,
    review_status: str | None,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    query = session.query(DataQualityJob)
    count_query = session.query(func.count(DataQualityJob.id))
    if status:
        query = query.filter(DataQualityJob.status == status)
        count_query = count_query.filter(DataQualityJob.status == status)
    if review_status:
        query = query.filter(DataQualityJob.review_status == review_status)
        count_query = count_query.filter(DataQualityJob.review_status == review_status)
    total = int(count_query.scalar() or 0)
    rows = (
        query.order_by(DataQualityJob.created_at.desc(), DataQualityJob.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [serialize_job(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": _pages(total, page_size),
    }


def mark_inline_execution(session: Session, job_id: int, *, execution_mode: str = "inline_degraded") -> None:
    """Record that a job ran in-request instead of through the Redis worker."""
    job = session.get(DataQualityJob, job_id)
    if job is None or job.execution_mode == execution_mode:
        return
    job.execution_mode = execution_mode
    job.updated_at = _utcnow()
    session.commit()


def mark_outbox_dispatched(session: Session, job_id: int) -> None:
    row = session.query(QualityTaskOutbox).filter(QualityTaskOutbox.job_id == job_id).first()
    if row is None:
        return
    row.status = "DISPATCHED"
    row.dispatched_at = _utcnow()
    row.last_error = None
    job = session.get(DataQualityJob, job_id)
    if job is not None and job.status == "PENDING":
        job.execution_mode = "async"
        job.updated_at = _utcnow()
    session.commit()


def mark_outbox_failed(session: Session, job_id: int, error: str) -> None:
    row = session.query(QualityTaskOutbox).filter(QualityTaskOutbox.job_id == job_id).first()
    if row is None:
        return
    row.status = "PENDING"
    row.attempts += 1
    row.last_error = error[:300]
    # Exponential-ish backoff capped at 60 seconds.
    delay = min(60, 2 ** min(row.attempts, 6))
    row.next_attempt_at = _utcnow() + datetime.timedelta(seconds=delay)
    session.commit()


def pending_outbox(session: Session, *, limit: int = 20, job_id: int | None = None) -> list[QualityTaskOutbox]:
    now = _utcnow()
    # MySQL DATETIME has second precision and may round a just-created value
    # up by <1s. A small dispatch tolerance prevents an accepted job from
    # being reported as UNAVAILABLE while the outbox row is already due.
    dispatch_before = now + datetime.timedelta(seconds=1)
    query = session.query(QualityTaskOutbox).filter(
        QualityTaskOutbox.status == "PENDING",
        QualityTaskOutbox.next_attempt_at <= dispatch_before,
    )
    if job_id is not None:
        query = query.filter(QualityTaskOutbox.job_id == job_id)
    return query.order_by(QualityTaskOutbox.id.asc()).limit(limit).all()


def claim_job(session: Session, job_id: int) -> int | None:
    """Atomically move PENDING -> RUNNING and return the fencing attempt.

    The returned attempt number is the execution ownership token. It is passed
    back to ``complete_job`` / ``fail_job`` so a worker whose lease expired
    cannot overwrite a newer execution.
    """
    now = _utcnow()
    try:
        result = session.execute(
            update(DataQualityJob)
            .where(
                DataQualityJob.id == job_id,
                DataQualityJob.status == "PENDING",
                DataQualityJob.attempts < DataQualityJob.max_attempts,
            )
            .values(
                status="RUNNING",
                attempts=DataQualityJob.attempts + 1,
                started_at=now,
                updated_at=now,
                version=DataQualityJob.version + 1,
                error_code=None,
                error_message=None,
            )
        )
        if not result.rowcount:
            session.rollback()
            return None
        attempt = session.execute(select(DataQualityJob.attempts).where(DataQualityJob.id == job_id)).scalar_one()
        session.commit()
        return int(attempt)
    except Exception:
        session.rollback()
        raise


def complete_job(
    session: Session,
    job_id: int,
    *,
    checked_rows: int,
    issues: Iterable[dict[str, Any]],
    request_id: str,
    actor: str,
    role: str,
    expected_attempt: int,
    execution_mode: str | None = None,
) -> DataQualityJob:
    drafts = list(issues)
    issue_count = len(drafts)
    now = _utcnow()
    values: dict[str, Any] = {
        "status": "SUCCEEDED",
        "issue_count": issue_count,
        "checked_rows": checked_rows,
        "finished_at": now,
        "updated_at": now,
        "version": DataQualityJob.version + 1,
    }
    if execution_mode:
        values["execution_mode"] = execution_mode

    result = session.execute(
        update(DataQualityJob)
        .where(
            DataQualityJob.id == job_id,
            DataQualityJob.status == "RUNNING",
            DataQualityJob.attempts == expected_attempt,
        )
        .values(**values)
    )
    if not result.rowcount:
        session.rollback()
        current = session.get(DataQualityJob, job_id)
        if current is None:
            raise AdminError(404, "JOB_NOT_FOUND", "质检任务不存在")
        raise AdminError(
            409,
            "EXECUTION_FENCED",
            "执行租约已失效，旧 Worker 不能提交结果",
            details={
                "expected_attempt": expected_attempt,
                "current_attempts": current.attempts,
                "current_status": current.status,
            },
        )

    for draft in drafts:
        session.add(
            DataQualityIssue(
                job_id=job_id,
                rule_code=draft["rule_code"],
                severity=draft["severity"],
                entity_type=draft["entity_type"],
                entity_id=int(draft.get("entity_id") or 0),
                field_name=draft.get("field_name") or "",
                message=draft["message"][:300],
                suggestion=(draft.get("suggestion") or "")[:300] or None,
            )
        )
    record_audit(
        session,
        request_id=request_id,
        actor=actor,
        role=role,
        action="quality_job.succeeded",
        resource_type="data_quality_job",
        resource_id=job_id,
        detail={
            "checked_rows": checked_rows,
            "issue_count": issue_count,
            "attempt": expected_attempt,
        },
    )
    session.commit()
    current = session.get(DataQualityJob, job_id)
    assert current is not None
    return current


def fail_job(
    session: Session,
    job_id: int,
    *,
    error_code: str,
    error_message: str,
    retryable: bool,
    request_id: str,
    actor: str,
    role: str,
    expected_attempt: int,
) -> DataQualityJob:
    job = session.get(DataQualityJob, job_id)
    if job is None:
        raise AdminError(404, "JOB_NOT_FOUND", "质检任务不存在")
    now = _utcnow()
    should_retry = retryable and expected_attempt < job.max_attempts
    values: dict[str, Any] = {
        "status": "PENDING" if should_retry else "FAILED",
        "error_code": error_code[:64],
        "error_message": error_message[:500],
        "updated_at": now,
        "version": DataQualityJob.version + 1,
    }
    if not should_retry:
        values["finished_at"] = now

    result = session.execute(
        update(DataQualityJob)
        .where(
            DataQualityJob.id == job_id,
            DataQualityJob.status == "RUNNING",
            DataQualityJob.attempts == expected_attempt,
        )
        .values(**values)
    )
    if not result.rowcount:
        session.rollback()
        current = session.get(DataQualityJob, job_id)
        if current is None:
            raise AdminError(404, "JOB_NOT_FOUND", "质检任务不存在")
        raise AdminError(
            409,
            "EXECUTION_FENCED",
            "执行租约已失效，旧 Worker 不能写入失败状态",
            details={
                "expected_attempt": expected_attempt,
                "current_attempts": current.attempts,
                "current_status": current.status,
            },
        )

    if should_retry:
        session.execute(
            update(QualityTaskOutbox)
            .where(QualityTaskOutbox.job_id == job_id)
            .values(
                status="PENDING",
                attempts=QualityTaskOutbox.attempts + 1,
                next_attempt_at=now + datetime.timedelta(seconds=min(60, 2 ** min(expected_attempt, 6))),
                last_error=error_message[:300],
            )
        )
    record_audit(
        session,
        request_id=request_id,
        actor=actor,
        role=role,
        action="quality_job.retry_scheduled" if should_retry else "quality_job.failed",
        resource_type="data_quality_job",
        resource_id=job_id,
        outcome="FAILURE" if not should_retry else "RETRY",
        detail={
            "error_code": error_code,
            "attempts": expected_attempt,
            "max_attempts": job.max_attempts,
        },
    )
    session.commit()
    current = session.get(DataQualityJob, job_id)
    assert current is not None
    return current


def review_job(
    session: Session,
    job_id: int,
    *,
    decision: str,
    note: str,
    expected_version: int,
    actor: str,
    role: str,
    request_id: str,
    ip_hash: str | None,
) -> DataQualityJob:
    job = session.get(DataQualityJob, job_id)
    if job is None:
        raise AdminError(404, "JOB_NOT_FOUND", "质检任务不存在")
    if job.status != "SUCCEEDED":
        raise AdminError(409, "INVALID_STATE_TRANSITION", "只有 SUCCEEDED 任务可以审核")
    if job.review_status != "PENDING_REVIEW":
        raise AdminError(409, "ALREADY_REVIEWED", "该任务已经审核过")
    if job.version != expected_version:
        raise AdminError(
            409,
            "VERSION_CONFLICT",
            "任务已被其他操作更新，请刷新后重试",
            details={"current_version": job.version, "expected_version": expected_version},
        )

    now = _utcnow()
    result = session.execute(
        update(DataQualityJob)
        .where(
            DataQualityJob.id == job_id,
            DataQualityJob.version == expected_version,
            DataQualityJob.status == "SUCCEEDED",
            DataQualityJob.review_status == "PENDING_REVIEW",
        )
        .values(
            review_status=decision,
            review_note=note or None,
            reviewed_by=actor,
            reviewed_at=now,
            updated_at=now,
            version=DataQualityJob.version + 1,
        )
    )
    if not result.rowcount:
        session.rollback()
        current = session.get(DataQualityJob, job_id)
        raise AdminError(
            409,
            "VERSION_CONFLICT",
            "任务已被其他操作更新，请刷新后重试",
            details={"current_version": current.version if current else None, "expected_version": expected_version},
        )
    record_audit(
        session,
        request_id=request_id,
        actor=actor,
        role=role,
        action="quality_job.reviewed",
        resource_type="data_quality_job",
        resource_id=job_id,
        detail={"decision": decision, "note": note[:200]},
        ip_hash=ip_hash,
    )
    session.commit()
    session.refresh(job)
    return job


def list_audit_logs(
    session: Session,
    *,
    action: str | None,
    actor: str | None,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    query = session.query(OperationAuditLog)
    count_query = session.query(func.count(OperationAuditLog.id))
    if action:
        query = query.filter(OperationAuditLog.action == action)
        count_query = count_query.filter(OperationAuditLog.action == action)
    if actor:
        query = query.filter(OperationAuditLog.actor == actor)
        count_query = count_query.filter(OperationAuditLog.actor == actor)
    total = int(count_query.scalar() or 0)
    rows = (
        query.order_by(OperationAuditLog.created_at.desc(), OperationAuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [serialize_audit(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": _pages(total, page_size),
    }


def requeue_orphaned_dispatched(
    session: Session,
    *,
    older_than_seconds: int = 60,
    limit: int = 50,
) -> int:
    """Re-arm jobs whose Redis message was lost before the DB claim.

    ``BRPOP`` removes the message from Redis before the worker performs the
    atomic ``PENDING -> RUNNING`` claim. If the worker dies in that window the
    job remains PENDING while its outbox row is already DISPATCHED.

    The outbox update is conditional on the job still being PENDING, so a
    concurrent worker claim wins and no duplicate re-arm is recorded.
    """
    threshold = _utcnow() - datetime.timedelta(seconds=older_than_seconds)
    rows = (
        session.query(DataQualityJob, QualityTaskOutbox)
        .join(QualityTaskOutbox, QualityTaskOutbox.job_id == DataQualityJob.id)
        .filter(
            DataQualityJob.status == "PENDING",
            QualityTaskOutbox.status == "DISPATCHED",
            DataQualityJob.updated_at < threshold,
        )
        .limit(limit)
        .all()
    )
    now = _utcnow()
    recovered = 0
    for job, _outbox in rows:
        still_pending = (
            select(DataQualityJob.id)
            .where(
                DataQualityJob.id == job.id,
                DataQualityJob.status == "PENDING",
                DataQualityJob.updated_at < threshold,
            )
            .exists()
        )
        result = session.execute(
            update(QualityTaskOutbox)
            .where(
                QualityTaskOutbox.job_id == job.id,
                QualityTaskOutbox.status == "DISPATCHED",
                still_pending,
            )
            .values(
                status="PENDING",
                attempts=QualityTaskOutbox.attempts + 1,
                next_attempt_at=now,
                dispatched_at=None,
                last_error="delivery lease expired before DB claim",
            )
        )
        recovered += int(bool(result.rowcount))
    if recovered:
        session.commit()
    else:
        session.rollback()
    return recovered


def requeue_stale_running(
    session: Session,
    *,
    older_than_seconds: int = 600,
    limit: int = 50,
) -> int:
    """Recover RUNNING jobs whose worker lease expired.

    Non-exhausted jobs go back to PENDING and re-arm their outbox row.
    Exhausted jobs become FAILED with a visible error code and failure audit.
    Every transition is a conditional UPDATE on the exact attempt, so two
    recovery workers cannot both apply the same transition.
    """
    threshold = _utcnow() - datetime.timedelta(seconds=older_than_seconds)
    rows = (
        session.query(DataQualityJob)
        .filter(
            DataQualityJob.status == "RUNNING",
            DataQualityJob.started_at.is_not(None),
            DataQualityJob.started_at < threshold,
        )
        .limit(limit)
        .all()
    )
    now = _utcnow()
    recovered = 0
    for job in rows:
        old_attempt = job.attempts
        exhausted = old_attempt >= job.max_attempts
        values: dict[str, Any] = {
            "status": "FAILED" if exhausted else "PENDING",
            "error_code": "WORKER_LEASE_EXPIRED",
            "error_message": (
                "Worker lease expired after max attempts; job marked FAILED"
                if exhausted
                else "Worker lease expired; job requeued for another attempt"
            ),
            "updated_at": now,
            "version": DataQualityJob.version + 1,
        }
        if exhausted:
            values["finished_at"] = now
        result = session.execute(
            update(DataQualityJob)
            .where(
                DataQualityJob.id == job.id,
                DataQualityJob.status == "RUNNING",
                DataQualityJob.attempts == old_attempt,
                DataQualityJob.started_at < threshold,
            )
            .values(**values)
        )
        if not result.rowcount:
            continue
        if not exhausted:
            session.execute(
                update(QualityTaskOutbox)
                .where(
                    QualityTaskOutbox.job_id == job.id,
                    QualityTaskOutbox.status == "DISPATCHED",
                )
                .values(
                    status="PENDING",
                    attempts=QualityTaskOutbox.attempts + 1,
                    next_attempt_at=now,
                    dispatched_at=None,
                    last_error="worker lease expired",
                )
            )
        record_audit(
            session,
            request_id=f"recovery-{job.id}-{old_attempt}",
            actor="system:recovery",
            role="system",
            action="quality_job.retry_scheduled" if not exhausted else "quality_job.failed",
            resource_type="data_quality_job",
            resource_id=job.id,
            outcome="RETRY" if not exhausted else "FAILURE",
            detail={
                "reason": "worker_lease_expired",
                "attempts": old_attempt,
                "max_attempts": job.max_attempts,
            },
        )
        recovered += 1
    if recovered:
        session.commit()
    else:
        session.rollback()
    return recovered
