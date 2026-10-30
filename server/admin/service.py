"""Business workflow for the operations workbench."""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from sqlalchemy.orm import Session

from server.admin import repository
from server.admin.errors import AdminError
from server.admin.queue import QueueUnavailable, get_queue, queue_state

logger = logging.getLogger(__name__)

TASK_MODES = {"auto", "async", "inline", "disabled"}


def task_mode() -> str:
    mode = os.getenv("QUALITY_TASK_MODE", "auto").strip().lower() or "auto"
    return mode if mode in TASK_MODES else "auto"


def _inline_allowed(mode: str) -> bool:
    if mode == "inline":
        return True
    return mode == "auto" and os.getenv("APP_ENV", "development").strip().lower() != "production"


def _publish_with_session(session: Session, job_id: int, queue) -> bool:
    rows = repository.pending_outbox(session, job_id=job_id)
    if not rows:
        return True
    try:
        queue.enqueue(job_id)
    except QueueUnavailable as exc:
        repository.mark_outbox_failed(session, job_id, str(exc))
        return False
    repository.mark_outbox_dispatched(session, job_id)
    return True


def create_quality_job(
    session: Session,
    *,
    filters: dict[str, Any],
    idempotency_key: str,
    actor: str,
    role: str,
    request_id: str,
    ip_hash: str | None,
) -> dict[str, Any]:
    mode = task_mode()
    if mode == "disabled":
        raise AdminError(503, "FEATURE_DISABLED", "数据质检功能已关闭（QUALITY_TASK_MODE=disabled）")

    key = (idempotency_key or "").strip()
    if not key:
        key = f"auto-{uuid.uuid4().hex}"
    if len(key) < 8 or len(key) > 80:
        raise AdminError(422, "VALIDATION_ERROR", "Idempotency-Key 长度必须在 8-80 之间")

    job, replayed = repository.create_job_with_outbox(
        session,
        filters=filters,
        idempotency_key=key,
        actor=actor,
        role=role,
        request_id=request_id,
        ip_hash=ip_hash,
    )
    if replayed:
        return {
            "job": repository.serialize_job(job),
            "replayed": True,
            "queue_state": "DISPATCHED" if job.execution_mode == "async" else "UNAVAILABLE",
            "warning": None,
        }

    if mode == "async":
        queue = get_queue()
        if queue is None:
            return {
                "job": repository.serialize_job(job),
                "replayed": False,
                "queue_state": "UNAVAILABLE",
                "warning": "REDIS_URL 未配置，任务已安全落库但尚未投递；配置 Redis 与 Worker 后会由 Outbox 重试",
            }
        if _publish_with_session(session, job.id, queue):
            return {
                "job": repository.serialize_job(job),
                "replayed": False,
                "queue_state": "DISPATCHED",
                "warning": None,
            }
        return {
            "job": repository.serialize_job(job),
            "replayed": False,
            "queue_state": "UNAVAILABLE",
            "warning": "Redis 暂不可用，任务保持 PENDING 并进入 Outbox 重试；未返回成功状态",
        }

    # auto / inline
    queue = get_queue()
    if mode == "auto" and queue is not None and queue.ping():
        if _publish_with_session(session, job.id, queue):
            return {
                "job": repository.serialize_job(job),
                "replayed": False,
                "queue_state": "DISPATCHED",
                "warning": None,
            }

    if not _inline_allowed(mode):
        return {
            "job": repository.serialize_job(job),
            "replayed": False,
            "queue_state": "UNAVAILABLE",
            "warning": "队列不可用，任务保持 PENDING；当前环境未启用内联降级",
        }

    from server.admin.worker import execute_job

    execute_job(
        job.id,
        session=session,
        actor=actor,
        role=role,
        request_id=request_id,
        execution_mode="inline_degraded",
    )
    repository.mark_outbox_dispatched(session, job.id)
    refreshed = repository.get_job(session, job.id)
    assert refreshed is not None
    return {
        "job": repository.serialize_job(refreshed),
        "replayed": False,
        "queue_state": "INLINE",
        "warning": "Redis 不可用，已在当前请求内同步执行质检（execution_mode=inline_degraded），状态为真实执行结果",
    }


def get_quality_job(session: Session, job_id: int) -> dict[str, Any]:
    detail = repository.get_job_detail(session, job_id)
    if detail is None:
        raise AdminError(404, "JOB_NOT_FOUND", "质检任务不存在")
    return detail


def list_quality_jobs(
    session: Session,
    *,
    status: str | None,
    review_status: str | None,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    if status and status not in repository.JOB_STATUSES:
        raise AdminError(422, "VALIDATION_ERROR", "status 取值非法", details={"allowed": repository.JOB_STATUSES})
    if review_status and review_status not in ("PENDING_REVIEW", "APPROVED", "REJECTED"):
        raise AdminError(422, "VALIDATION_ERROR", "review_status 取值非法")
    return repository.list_jobs(
        session,
        status=status,
        review_status=review_status,
        page=page,
        page_size=page_size,
    )


def review_quality_job(
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
) -> dict[str, Any]:
    if decision not in ("APPROVED", "REJECTED"):
        raise AdminError(422, "VALIDATION_ERROR", "decision 必须是 APPROVED 或 REJECTED")
    job = repository.review_job(
        session,
        job_id,
        decision=decision,
        note=note,
        expected_version=expected_version,
        actor=actor,
        role=role,
        request_id=request_id,
        ip_hash=ip_hash,
    )
    return repository.serialize_job(job)


def statistics(session: Session) -> dict[str, Any]:
    return repository.get_stats(session)


def system_status(session: Session) -> dict[str, Any]:
    from server.admin.auth import AdminConfigError, get_admin_config

    try:
        config = get_admin_config()
        enabled = config.enabled
        source = config.source
    except AdminConfigError:
        enabled = False
        source = "invalid"

    bind = session.get_bind()
    dialect = bind.dialect.name if bind is not None else "unknown"
    mode = task_mode()
    queue = get_queue() if mode != "disabled" else None
    state = queue_state(queue) if queue is not None else "DISABLED"
    hint = {
        "auto": "优先 Redis 异步；开发环境 Redis 不可用时显式内联降级",
        "async": "仅 Redis 异步；队列不可用时任务保持 PENDING",
        "inline": "同步执行（演示/测试）",
        "disabled": "质检功能关闭",
    }[mode]
    return {
        "admin_enabled": enabled,
        "config_source": source,
        "database_dialect": dialect,
        "task_mode": mode,
        "queue_state": state,
        "worker_hint": hint,
    }
