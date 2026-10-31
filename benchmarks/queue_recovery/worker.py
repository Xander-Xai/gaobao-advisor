"""Worker processes used by the queue-recovery experiment.

Fault hooks pause the child at a precise point; the parent performs a real
SIGKILL, so Redis/MySQL state is produced by an actual process death. The
business path is the production ``execute_job`` implementation.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

SHORT_CONFIG = {
    "WORKER_DELIVERY_LEASE_SECONDS": "4",
    "WORKER_RECOVERY_INTERVAL_SECONDS": "1",
    "WORKER_LEASE_SECONDS": "4",
}
DEFAULT_CONFIG = {
    "WORKER_DELIVERY_LEASE_SECONDS": "60",
    "WORKER_RECOVERY_INTERVAL_SECONDS": "30",
    "WORKER_LEASE_SECONDS": "600",
}


def _apply_env(mysql_url: str, redis_url: str, config: dict[str, str] | None) -> None:
    os.environ["DATABASE_URL"] = mysql_url
    os.environ["REDIS_URL"] = redis_url
    os.environ["QUALITY_TASK_MODE"] = "async"
    for key, value in (config or SHORT_CONFIG).items():
        os.environ[key] = str(value)


def _write_event(event_dir: str, name: str, payload: dict[str, Any]) -> None:
    path = Path(event_dir)
    path.mkdir(parents=True, exist_ok=True)
    target = path / f"{name}.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
    temporary.replace(target)


def _append_event(event_dir: str, worker_id: str, payload: dict[str, Any]) -> None:
    path = Path(event_dir)
    path.mkdir(parents=True, exist_ok=True)
    with (path / f"{worker_id}.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def _marker(event_dir: str, name: str, worker_id: str, payload: dict[str, Any]) -> None:
    _write_event(event_dir, f"{name}.{worker_id}", payload)


def _pause_for_parent(event_dir: str, name: str, worker_id: str, payload: dict[str, Any]) -> None:
    payload = {**payload, "monotonic": time.monotonic()}
    _marker(event_dir, name, worker_id, payload)
    _append_event(event_dir, worker_id, {"type": name, **payload})
    time.sleep(120)


def _install_claim_hook(event_dir: str, worker_id: str) -> Any:
    from server.admin import repository

    original = repository.claim_job

    def hooked_claim(session, job_id):
        attempt = original(session, job_id)
        _append_event(
            event_dir,
            worker_id,
            {
                "type": "claim",
                "job_id": job_id,
                "attempt": attempt,
                "monotonic": time.monotonic(),
            },
        )
        return attempt

    repository.claim_job = hooked_claim
    return original


def _adapter_with_retry(
    scheme: str,
    redis_url: str,
    run_id: str,
    consumer: str | None,
    deadline: float,
    event_dir: str,
    worker_id: str,
):
    from benchmarks.queue_recovery.adapters import make_adapter

    while True:
        try:
            return make_adapter(scheme, redis_url, run_id=run_id, consumer=consumer)
        except Exception as exc:
            if time.monotonic() >= deadline:
                raise
            _append_event(
                event_dir,
                worker_id,
                {
                    "type": "adapter_retry",
                    "error": f"{type(exc).__name__}: {exc}",
                    "monotonic": time.monotonic(),
                },
            )
            time.sleep(0.5)


def run_worker_process(
    *,
    scheme: str,
    mysql_url: str,
    redis_url: str,
    run_id: str,
    worker_id: str,
    event_dir: str,
    fault: str = "",
    max_jobs: int = 1,
    idle_seconds: int = 2,
    consumer: str | None = None,
    config: dict[str, str] | None = None,
    max_runtime: float = 60.0,
) -> None:
    _apply_env(mysql_url, redis_url, config)

    import db.models  # noqa: F401
    from db.database import engine as db_engine

    db_engine.dispose()
    import server.admin.worker as worker_module
    from server.admin.worker import execute_job

    adapter = _adapter_with_retry(
        scheme,
        redis_url,
        run_id,
        consumer,
        time.monotonic() + max_runtime,
        event_dir,
        worker_id,
    )
    original_collect = worker_module.collect_issues
    original_claim = _install_claim_hook(event_dir, worker_id)
    state: dict[str, int | None] = {"job_id": None}

    def hooked_collect(session, filters):
        if fault == "after_claim":
            _pause_for_parent(
                event_dir,
                "after_claim",
                worker_id,
                {"worker_id": worker_id, "job_id": state["job_id"], "scheme": scheme},
            )
        checked_rows, issues = original_collect(session, filters)
        if fault == "during_execute":
            _pause_for_parent(
                event_dir,
                "during_execute",
                worker_id,
                {"worker_id": worker_id, "job_id": state["job_id"], "scheme": scheme},
            )
        return checked_rows, issues

    worker_module.collect_issues = hooked_collect
    processed = 0
    idle_deadline = time.monotonic() + max(1, idle_seconds)
    deadline = time.monotonic() + max_runtime
    try:
        while (processed < max_jobs or max_jobs <= 0) and time.monotonic() < deadline:
            if hasattr(adapter, "dispatch_due"):
                try:
                    adapter.dispatch_due()
                except Exception as exc:
                    _append_event(
                        event_dir,
                        worker_id,
                        {
                            "type": "worker_error",
                            "phase": "dispatch",
                            "error": f"{type(exc).__name__}: {exc}",
                            "monotonic": time.monotonic(),
                        },
                    )
                    time.sleep(0.5)
                    continue
            if fault == "before_consume":
                _pause_for_parent(
                    event_dir,
                    "before_consume",
                    worker_id,
                    {"worker_id": worker_id, "scheme": scheme},
                )
            try:
                delivery = adapter.consume_one(timeout=1)
            except Exception as exc:
                _append_event(
                    event_dir,
                    worker_id,
                    {
                        "type": "worker_error",
                        "phase": "consume",
                        "error": f"{type(exc).__name__}: {exc}",
                        "monotonic": time.monotonic(),
                    },
                )
                time.sleep(0.5)
                continue
            if delivery is None:
                if processed >= max_jobs and max_jobs > 0:
                    break
                if time.monotonic() >= idle_deadline:
                    break
                continue
            idle_deadline = time.monotonic() + max(1, idle_seconds)
            state["job_id"] = delivery.job_id
            started = time.monotonic()
            _append_event(
                event_dir,
                worker_id,
                {
                    "type": "consumed",
                    "worker_id": worker_id,
                    "job_id": delivery.job_id,
                    "scheme": scheme,
                    "delivery_id": delivery.delivery_id,
                    "monotonic": started,
                },
            )
            if fault == "after_consume":
                _pause_for_parent(
                    event_dir,
                    "after_consume",
                    worker_id,
                    {"worker_id": worker_id, "job_id": delivery.job_id, "scheme": scheme},
                )
            try:
                result = execute_job(delivery.job_id, execution_mode="async")
            except Exception as exc:
                _append_event(
                    event_dir,
                    worker_id,
                    {
                        "type": "worker_error",
                        "phase": "execute",
                        "job_id": delivery.job_id,
                        "error": f"{type(exc).__name__}: {exc}",
                        "monotonic": time.monotonic(),
                    },
                )
                time.sleep(0.5)
                continue
            finished = time.monotonic()
            _append_event(
                event_dir,
                worker_id,
                {
                    "type": "execution",
                    "job_id": delivery.job_id,
                    "scheme": scheme,
                    "status": result.get("status"),
                    "started_monotonic": started,
                    "finished_monotonic": finished,
                    "attempts": result.get("attempts"),
                    "issue_count": result.get("issue_count"),
                },
            )
            if fault == "after_db_before_ack":
                _pause_for_parent(
                    event_dir,
                    "after_db_before_ack",
                    worker_id,
                    {"worker_id": worker_id, "job_id": delivery.job_id, "scheme": scheme},
                )
            try:
                adapter.ack(delivery)
            except Exception as exc:
                _append_event(
                    event_dir,
                    worker_id,
                    {
                        "type": "worker_error",
                        "phase": "ack",
                        "job_id": delivery.job_id,
                        "error": f"{type(exc).__name__}: {exc}",
                        "monotonic": time.monotonic(),
                    },
                )
                time.sleep(0.5)
                continue
            _append_event(
                event_dir,
                worker_id,
                {
                    "type": "ack",
                    "job_id": delivery.job_id,
                    "delivery_id": delivery.delivery_id,
                    "monotonic": time.monotonic(),
                },
            )
            processed += 1
            if fault == "after_ack_crash":
                _pause_for_parent(
                    event_dir,
                    "after_ack_crash",
                    worker_id,
                    {"worker_id": worker_id, "job_id": delivery.job_id, "scheme": scheme},
                )
    finally:
        worker_module.collect_issues = original_collect
        from server.admin import repository

        repository.claim_job = original_claim
        adapter.close()


def run_recovery_process(
    *,
    scheme: str,
    mysql_url: str,
    redis_url: str,
    run_id: str,
    worker_id: str,
    event_dir: str,
    lease_seconds: float = 2.0,
    consumer: str | None = None,
    config: dict[str, str] | None = None,
) -> None:
    _apply_env(mysql_url, redis_url, config)

    import db.models  # noqa: F401
    from db.database import engine as db_engine

    db_engine.dispose()
    from server.admin.worker import execute_job, recover_worker_state

    adapter = _adapter_with_retry(
        scheme,
        redis_url,
        run_id,
        consumer,
        time.monotonic() + 15.0,
        event_dir,
        worker_id,
    )
    _append_event(
        event_dir,
        worker_id,
        {"type": "recovery_start", "scheme": scheme, "monotonic": time.monotonic()},
    )
    original_claim = _install_claim_hook(event_dir, worker_id)
    try:
        started = time.monotonic()
        orphaned_seconds = int(lease_seconds) if scheme == "list" else 10**9
        recover_worker_state(
            stale_running_seconds=int(lease_seconds),
            orphaned_seconds=orphaned_seconds,
            limit=100,
        )
        db_scan = time.monotonic() - started
        started = time.monotonic()
        deadline = time.monotonic() + max(8.0, lease_seconds + 3.0)
        stale = adapter.stale(lease_seconds=lease_seconds)
        while not stale and adapter.pending_count() and time.monotonic() < deadline:
            time.sleep(0.25)
            recover_worker_state(
                stale_running_seconds=int(lease_seconds),
                orphaned_seconds=orphaned_seconds,
                limit=100,
            )
            stale = adapter.stale(lease_seconds=lease_seconds)
        if stale:
            recover_worker_state(
                stale_running_seconds=int(lease_seconds),
                orphaned_seconds=orphaned_seconds,
                limit=100,
            )
        delivery_scan = time.monotonic() - started
        _append_event(
            event_dir,
            worker_id,
            {
                "type": "recovery_scan",
                "scheme": scheme,
                "db_scan_s": round(db_scan, 4),
                "delivery_scan_s": round(delivery_scan, 4),
                "stale_count": len(stale),
                "monotonic": time.monotonic(),
            },
        )
        for delivery in stale:
            if not adapter.claim_stale(delivery, lease_seconds=lease_seconds):
                _append_event(
                    event_dir,
                    worker_id,
                    {
                        "type": "recovery_skip",
                        "job_id": delivery.job_id,
                        "delivery_id": delivery.delivery_id,
                        "scheme": scheme,
                        "monotonic": time.monotonic(),
                    },
                )
                continue
            _marker(
                event_dir,
                "recovered",
                worker_id,
                {
                    "worker_id": worker_id,
                    "job_id": delivery.job_id,
                    "delivery_id": delivery.delivery_id,
                    "scheme": scheme,
                    "monotonic": time.monotonic(),
                },
            )
            retry_deadline = time.monotonic() + 8.0
            result = execute_job(delivery.job_id, execution_mode="async")
            while result.get("status") not in {"SUCCEEDED", "FAILED", "MISSING"} and time.monotonic() < retry_deadline:
                time.sleep(0.5)
                recover_worker_state(
                    stale_running_seconds=int(lease_seconds),
                    orphaned_seconds=orphaned_seconds,
                    limit=100,
                )
                result = execute_job(delivery.job_id, execution_mode="async")
            if result.get("status") in {"SUCCEEDED", "FAILED", "MISSING"}:
                if scheme != "list":
                    from db.database import SessionLocal
                    from server.admin import repository

                    session = SessionLocal()
                    try:
                        repository.mark_outbox_dispatched(session, delivery.job_id)
                    finally:
                        session.close()
                    _append_event(
                        event_dir,
                        worker_id,
                        {
                            "type": "outbox_marked",
                            "job_id": delivery.job_id,
                            "monotonic": time.monotonic(),
                        },
                    )
                adapter.discard(delivery)
                _append_event(
                    event_dir,
                    worker_id,
                    {
                        "type": "ack",
                        "job_id": delivery.job_id,
                        "delivery_id": delivery.delivery_id,
                        "monotonic": time.monotonic(),
                        "source": "recovery",
                    },
                )
            else:
                adapter.requeue(delivery)
    finally:
        from server.admin import repository

        repository.claim_job = original_claim
        adapter.close()


def run_production_worker(
    *,
    mysql_url: str,
    redis_url: str,
    run_id: str,
    event_dir: str,
    worker_id: str,
    queue_key: str,
    config: dict[str, str] | None = None,
    max_runtime: float = 180.0,
) -> None:
    _apply_env(mysql_url, redis_url, config or DEFAULT_CONFIG)
    os.environ["QUALITY_QUEUE_KEY"] = queue_key

    import logging

    logging.basicConfig(level=logging.WARNING)
    import db.models  # noqa: F401
    from db.database import engine as db_engine

    db_engine.dispose()
    import server.admin.worker as worker_module

    _append_event(
        event_dir,
        worker_id,
        {
            "type": "production_start",
            "queue_key": queue_key,
            "config": dict(config or DEFAULT_CONFIG),
            "monotonic": time.monotonic(),
        },
    )
    original_claim = _install_claim_hook(event_dir, worker_id)
    deadline = time.monotonic() + max_runtime
    try:
        while time.monotonic() < deadline:
            try:
                worker_module.run_forever(timeout=1)
            except KeyboardInterrupt:
                return
            except Exception as exc:
                _append_event(
                    event_dir,
                    worker_id,
                    {"type": "worker_error", "error": f"{type(exc).__name__}: {exc}", "monotonic": time.monotonic()},
                )
                time.sleep(1)
    finally:
        from server.admin import repository

        repository.claim_job = original_claim
