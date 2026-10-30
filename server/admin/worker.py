"""Data-quality worker.

Run separately from the API (``python -m server.admin.worker``). It consumes
job ids from Redis, claims the corresponding database row with an atomic
``PENDING -> RUNNING`` update, runs deterministic checks, persists findings and
records an audit event.

Failure policy: transient errors requeue the job until ``max_attempts``;
permanent or exhausted failures become ``FAILED`` with a visible error code.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import signal
import time
import uuid
from typing import Any

from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as SATimeoutError
from sqlalchemy.orm import Session

from db.database import SessionLocal
from db.models import DataQualityJob
from server.admin import repository
from server.admin.logging import log_error, log_event
from server.admin.quality import collect_issues
from server.admin.queue import QueueUnavailable, dispatch_outbox, get_queue

logger = logging.getLogger(__name__)

_REDACT_RE = re.compile(r"://([^:/@\s]+):([^@/\s]+)@")


class RetryableJobError(RuntimeError):
    """Raised for transient failures that should be retried."""


def _redact(value: str) -> str:
    return _REDACT_RE.sub(r"://\1:***@", value)[:500]


def _result(job: DataQualityJob | None) -> dict[str, Any]:
    if job is None:
        return {"job_id": None, "status": "MISSING"}
    return {
        "job_id": job.id,
        "status": job.status,
        "attempts": job.attempts,
        "issue_count": job.issue_count,
        "checked_rows": job.checked_rows,
        "error_code": job.error_code,
    }


def execute_job(
    job_id: int,
    *,
    session: Session | None = None,
    actor: str = "system:worker",
    role: str = "system",
    request_id: str | None = None,
    execution_mode: str = "async",
) -> dict[str, Any]:
    """Claim and execute one job. Safe to call concurrently for the same id."""
    request_id = request_id or f"worker-{uuid.uuid4().hex[:16]}"
    owns_session = session is None
    db = session or SessionLocal()
    started = time.monotonic()
    try:
        if not repository.claim_job(db, job_id):
            job = repository.get_job(db, job_id)
            log_event("quality_job.claim_skipped", job_id=job_id, status=job.status if job else None)
            return _result(job)

        repository.record_audit(
            db,
            request_id=request_id,
            actor=actor,
            role=role,
            action="quality_job.started",
            resource_type="data_quality_job",
            resource_id=job_id,
            detail={"execution_mode": execution_mode},
        )
        db.commit()

        job = repository.get_job(db, job_id)
        if job is None:
            raise RetryableJobError("job disappeared after claim")
        try:
            filters = json.loads(job.filters_json or "{}")
        except json.JSONDecodeError:
            filters = {}
        if not isinstance(filters, dict):
            filters = {}

        checked_rows, issues = collect_issues(db, filters)
        finished = repository.complete_job(
            db,
            job_id,
            checked_rows=checked_rows,
            issues=issues,
            request_id=request_id,
            actor=actor,
            role=role,
            execution_mode=execution_mode,
        )
        elapsed_ms = int((time.monotonic() - started) * 1000)
        log_event(
            "quality_job.succeeded",
            job_id=job_id,
            issue_count=finished.issue_count,
            checked_rows=checked_rows,
            elapsed_ms=elapsed_ms,
        )
        return _result(finished)
    except Exception as exc:  # noqa: BLE001 - failure must be persisted, then surfaced
        db.rollback()
        retryable = isinstance(exc, (RetryableJobError, OperationalError, SATimeoutError, TimeoutError))
        message = _redact(f"{type(exc).__name__}: {exc}")
        error_code = "QUALITY_JOB_TRANSIENT" if retryable else "QUALITY_JOB_FAILED"
        try:
            failed = repository.fail_job(
                db,
                job_id,
                error_code=error_code,
                error_message=message,
                retryable=retryable,
                request_id=request_id,
                actor=actor,
                role=role,
            )
        except Exception:  # pragma: no cover - last-resort diagnostics
            log_error("quality_job.failure_persist_failed", job_id=job_id, error=message)
            raise
        log_error(
            "quality_job.failed",
            job_id=job_id,
            error_code=error_code,
            retryable=retryable,
            status=failed.status,
            attempts=failed.attempts,
        )
        return _result(failed)
    finally:
        if owns_session:
            db.close()


def run_once(*, timeout: int = 2, queue=None, db: Session | None = None) -> dict[str, Any]:
    """Dispatch due outbox rows, then process at most one queued job."""
    active_queue = queue or get_queue()
    if active_queue is None:
        raise QueueUnavailable("REDIS_URL is not configured; the worker has no queue")
    dispatch_outbox(limit=20, queue=active_queue)
    job_id = active_queue.dequeue(timeout=timeout)
    if job_id is None:
        return {"job_id": None, "status": "IDLE"}
    if db is not None:
        return execute_job(job_id, session=db)
    return execute_job(job_id)


def run_forever(*, timeout: int = 2) -> None:
    stop = {"flag": False}

    def _stop(signum, frame):  # noqa: ARG001
        stop["flag"] = True
        logger.info("worker received signal %s, stopping after current job", signum)

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    queue = get_queue()
    if queue is None:
        raise QueueUnavailable("REDIS_URL is not configured; refusing to start a worker without a queue")

    # Recover jobs left RUNNING by a crashed worker before consuming new work.
    session = SessionLocal()
    try:
        recovered = repository.requeue_stale_running(session)
        if recovered:
            logger.warning("requeued %d stale RUNNING job(s)", recovered)
    finally:
        session.close()

    logger.info("quality worker started, queue=%s key=%s", queue.url, queue.key)
    while not stop["flag"]:
        try:
            result = run_once(timeout=timeout, queue=queue)
            if result.get("job_id"):
                log_event("worker.processed", **result)
        except QueueUnavailable as exc:
            logger.warning("queue unavailable: %s; retrying in 3s", exc)
            time.sleep(3)
        except Exception:  # pragma: no cover - worker must stay alive
            logger.exception("unexpected worker loop error; retrying in 3s")
            time.sleep(3)
    logger.info("quality worker stopped")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="gaobao data-quality worker")
    parser.add_argument("--once", action="store_true", help="dispatch outbox and process at most one job")
    parser.add_argument("--timeout", type=int, default=2, help="BRPOP timeout seconds")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        if args.once:
            print(json.dumps(run_once(timeout=args.timeout), ensure_ascii=False))
        else:
            run_forever(timeout=args.timeout)
    except QueueUnavailable as exc:
        logger.error("worker cannot start: %s", exc)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
