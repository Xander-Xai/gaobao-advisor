"""Synthetic workload and MySQL state snapshots for queue recovery experiments."""

from __future__ import annotations

import datetime
import os
import uuid
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

QUEUE_PREFIX = "gaobao:qr"


def prepare_database(url: str, *, schools: int = 200, scores_per_school: int = 5):
    """Create a guarded benchmark schema and synthetic schools."""
    from benchmarks.guard import ensure_benchmark_database
    from db.database import Base
    from scripts.benchmark_admin_queries import build_dataset

    os.environ["DATABASE_URL"] = url
    engine = create_engine(url, pool_pre_ping=True, pool_recycle=1800)
    ensure_benchmark_database(engine, url, allow_database_url_match=True)
    with engine.begin() as connection:
        connection.execute(text("SET FOREIGN_KEY_CHECKS=0"))
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = factory()
    try:
        build_dataset(session, schools, scores_per_school)
    finally:
        session.close()
    return engine, factory


def create_jobs(factory, count: int, *, max_attempts: int = 3, prefix: str = "qr") -> list[int]:
    from server.admin import repository

    session = factory()
    ids: list[int] = []
    try:
        for index in range(count):
            job, _ = repository.create_job_with_outbox(
                session,
                filters={"province": ["示例省·甲", "示例省·乙", "示例省·丙", "示例省·丁"][index % 4]},
                idempotency_key=f"{prefix}-{uuid.uuid4().hex}",
                actor="benchmark",
                role="operator",
                request_id=f"qr-{index}",
                ip_hash=None,
                max_attempts=max_attempts,
            )
            ids.append(job.id)
    finally:
        session.close()
    return ids


def mark_dispatched(factory, job_ids: list[int]) -> None:
    from db.models import QualityTaskOutbox

    session = factory()
    try:
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        session.query(QualityTaskOutbox).filter(QualityTaskOutbox.job_id.in_(job_ids)).update(
            {"status": "DISPATCHED", "dispatched_at": now},
            synchronize_session=False,
        )
        session.commit()
    finally:
        session.close()


def snapshot(factory, job_ids: list[int]) -> dict[str, Any]:
    from sqlalchemy import func

    from db.models import DataQualityIssue, DataQualityJob, OperationAuditLog, QualityTaskOutbox

    session = factory()
    try:
        jobs = session.query(DataQualityJob).filter(DataQualityJob.id.in_(job_ids)).all()
        outboxes = session.query(QualityTaskOutbox).filter(QualityTaskOutbox.job_id.in_(job_ids)).all()
        audit_rows = (
            session.query(OperationAuditLog.action, func.count(OperationAuditLog.id))
            .filter(OperationAuditLog.resource_id.in_([str(item) for item in job_ids]))
            .group_by(OperationAuditLog.action)
            .all()
        )
        audit = {str(action): int(count) for action, count in audit_rows}
        issues = session.query(DataQualityIssue).filter(DataQualityIssue.job_id.in_(job_ids)).count()
        duplicate_issue_groups = (
            session.query(DataQualityIssue.job_id)
            .filter(DataQualityIssue.job_id.in_(job_ids))
            .group_by(
                DataQualityIssue.job_id,
                DataQualityIssue.rule_code,
                DataQualityIssue.entity_type,
                DataQualityIssue.entity_id,
                DataQualityIssue.field_name,
            )
            .having(func.count(DataQualityIssue.id) > 1)
            .count()
        )
        return {
            "jobs": [
                {
                    "id": job.id,
                    "status": job.status,
                    "attempts": job.attempts,
                    "max_attempts": job.max_attempts,
                    "issue_count": job.issue_count,
                    "checked_rows": job.checked_rows,
                    "error_code": job.error_code,
                    "started_at": job.started_at.isoformat() if job.started_at else None,
                    "finished_at": job.finished_at.isoformat() if job.finished_at else None,
                }
                for job in jobs
            ],
            "outbox": [
                {"job_id": row.job_id, "status": row.status, "attempts": row.attempts, "last_error": row.last_error}
                for row in outboxes
            ],
            "audit": audit,
            "audit_created": audit.get("quality_job.created", 0),
            "audit_started": audit.get("quality_job.started", 0),
            "audit_succeeded": audit.get("quality_job.succeeded", 0),
            "audit_failed": audit.get("quality_job.failed", 0),
            "audit_retry": audit.get("quality_job.retry_scheduled", 0),
            "issue_rows": issues,
            "duplicate_issue_groups": duplicate_issue_groups,
        }
    finally:
        session.close()


def reset_outbox_for_retry(factory, job_ids: list[int]) -> None:
    """Re-arm outbox rows for the List/Outbox recovery path."""
    from db.models import QualityTaskOutbox

    session = factory()
    try:
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        session.query(QualityTaskOutbox).filter(QualityTaskOutbox.job_id.in_(job_ids)).update(
            {"status": "PENDING", "next_attempt_at": now, "dispatched_at": None},
            synchronize_session=False,
        )
        session.commit()
    finally:
        session.close()
