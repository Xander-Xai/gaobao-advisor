"""Run the Issue #40 delivery-model comparison.

Examples::

    MYSQL_BENCH_URL=... REDIS_BENCH_URL=... \
      python -m benchmarks.queue_recovery.runner --suite fault --repeats 3

The runner only creates its own guarded benchmark schema and random Redis
keys. It never flushes a shared Redis instance.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import signal
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy.engine import make_url

from benchmarks.queue_recovery.metrics import docker_stats, summarize

SCHEMES = ("list", "blmove", "streams")
SCENARIOS = (
    "published_not_consumed",
    "after_consume",
    "after_claim",
    "during_execute",
    "after_db_before_ack",
    "after_ack_crash",
    "duplicate_delivery",
    "two_recoverers",
    "redis_unavailable",
    "redis_restart",
    "mysql_unavailable",
    "max_attempts",
)
LIST_NOT_APPLICABLE = frozenset({"after_db_before_ack", "after_ack_crash"})
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


def _set_environment(mysql_url: str, redis_url: str, config: dict[str, str] | None = None) -> None:
    os.environ["DATABASE_URL"] = mysql_url
    os.environ["REDIS_URL"] = redis_url
    os.environ["QUALITY_TASK_MODE"] = "async"
    os.environ["DB_CONNECT_TIMEOUT"] = "2"
    os.environ["DB_POOL_SIZE"] = "3"
    os.environ["DB_MAX_OVERFLOW"] = "2"
    for key, value in (config or SHORT_CONFIG).items():
        os.environ[key] = str(value)


def _mp_context():
    try:
        return multiprocessing.get_context("fork")
    except ValueError:
        return multiprocessing.get_context("spawn")


def _database_identity(url: str) -> dict[str, Any]:
    parsed = make_url(url)
    return {
        "backend": parsed.get_backend_name(),
        "host": parsed.host,
        "port": parsed.port or 3306,
        "database": parsed.database,
    }


def _docker(*args: str, timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _docker_password(mysql_url: str) -> str:
    return make_url(mysql_url).password or ""


def _wait_mysql_ready(mysql_url: str, container: str, timeout: float = 90.0) -> None:
    password = _docker_password(mysql_url)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        completed = subprocess.run(
            ["docker", "exec", container, "mysqladmin", "ping", "-h127.0.0.1", "-uroot", f"-p{password}", "--silent"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if completed.returncode == 0:
            return
        time.sleep(0.5)
    raise TimeoutError(f"MySQL container {container} did not become ready")


def _wait_redis_ready(redis_url: str, timeout: float = 60.0) -> None:
    import redis

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        client = redis.Redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=2)
        try:
            if client.ping():
                return
        except Exception:
            pass
        finally:
            client.close()
        time.sleep(0.2)
    raise TimeoutError("Redis did not become ready")


def _save_adapter(adapter) -> None:
    try:
        if hasattr(adapter, "queue"):
            adapter.queue._connect().save()  # noqa: SLF001 - experiment persistence hook
        else:
            adapter.client.save()
    except Exception:
        pass


def _wait_marker(path: Path, timeout: float = 20.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        time.sleep(0.02)
    raise TimeoutError(f"worker fault marker not observed: {path}")


def _start_worker(
    *,
    scheme: str,
    mysql_url: str,
    redis_url: str,
    run_id: str,
    worker_id: str,
    event_dir: Path,
    fault: str = "",
    max_jobs: int = 1,
    idle_seconds: int = 3,
    consumer: str | None = None,
    config: dict[str, str] | None = None,
    max_runtime: float = 60.0,
) -> multiprocessing.Process:
    from benchmarks.queue_recovery.worker import run_worker_process

    ctx = _mp_context()
    process = ctx.Process(
        target=run_worker_process,
        kwargs={
            "scheme": scheme,
            "mysql_url": mysql_url,
            "redis_url": redis_url,
            "run_id": run_id,
            "worker_id": worker_id,
            "event_dir": str(event_dir),
            "fault": fault,
            "max_jobs": max_jobs,
            "idle_seconds": idle_seconds,
            "consumer": consumer,
            "config": config or SHORT_CONFIG,
            "max_runtime": max_runtime,
        },
        daemon=True,
    )
    process.start()
    return process


def _start_recovery(
    *,
    scheme: str,
    mysql_url: str,
    redis_url: str,
    run_id: str,
    worker_id: str,
    event_dir: Path,
    consumer: str | None = None,
) -> multiprocessing.Process:
    from benchmarks.queue_recovery.worker import run_recovery_process

    ctx = _mp_context()
    process = ctx.Process(
        target=run_recovery_process,
        kwargs={
            "scheme": scheme,
            "mysql_url": mysql_url,
            "redis_url": redis_url,
            "run_id": run_id,
            "worker_id": worker_id,
            "event_dir": str(event_dir),
            "lease_seconds": 2.0,
            "consumer": consumer,
            "config": SHORT_CONFIG,
        },
        daemon=True,
    )
    from benchmarks.queue_recovery.worker import _append_event

    _append_event(str(event_dir), "parent", {"type": "parent_recovery_launch", "monotonic": time.monotonic()})
    process.start()
    return process


def _start_production_worker(
    *,
    mysql_url: str,
    redis_url: str,
    run_id: str,
    event_dir: Path,
    worker_id: str,
    queue_key: str,
    max_runtime: float = 180.0,
) -> multiprocessing.Process:
    from benchmarks.queue_recovery.worker import run_production_worker

    ctx = _mp_context()
    process = ctx.Process(
        target=run_production_worker,
        kwargs={
            "mysql_url": mysql_url,
            "redis_url": redis_url,
            "run_id": run_id,
            "event_dir": str(event_dir),
            "worker_id": worker_id,
            "queue_key": queue_key,
            "config": DEFAULT_CONFIG,
            "max_runtime": max_runtime,
        },
        daemon=True,
    )
    process.start()
    return process


def _kill(process: multiprocessing.Process) -> None:
    if process.is_alive():
        os.kill(process.pid, signal.SIGKILL)
    process.join(timeout=10)


def _terminate(process: multiprocessing.Process) -> None:
    if process.is_alive():
        os.kill(process.pid, signal.SIGTERM)
    process.join(timeout=5)
    if process.is_alive():
        _kill(process)


def _join(process: multiprocessing.Process, timeout: float = 30.0) -> None:
    process.join(timeout=timeout)
    if process.is_alive():
        _kill(process)


def _wait_terminal(
    factory,
    adapter,
    job_id: int,
    *,
    timeout: float = 45.0,
    require_cleanup: bool = True,
) -> tuple[dict[str, Any], float | None, float | None, int | None]:
    from benchmarks.queue_recovery.workload import snapshot

    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    terminal_at: float | None = None
    cleanup_at: float | None = None
    pending: int | None = None
    while time.monotonic() < deadline:
        try:
            last = snapshot(factory, [job_id])
        except Exception:
            time.sleep(0.1)
            continue
        jobs = last.get("jobs") or []
        status = jobs[0]["status"] if jobs else "MISSING"
        if status in {"SUCCEEDED", "FAILED", "MISSING"} and terminal_at is None:
            terminal_at = time.monotonic()
        if status in {"SUCCEEDED", "FAILED", "MISSING"}:
            try:
                pending = adapter.pending_count()
            except Exception:
                pending = -1
            if not require_cleanup or pending == 0:
                cleanup_at = time.monotonic()
                break
        time.sleep(0.05)
    return last, terminal_at, cleanup_at, pending


def _events(event_dir: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for path in sorted(event_dir.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    result.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    for path in sorted(event_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        payload.setdefault("type", path.name.split(".", 1)[0])
        payload["source_file"] = path.name
        result.append(payload)
    return result


def _count(events: list[dict[str, Any]], event_type: str, **match: Any) -> int:
    total = 0
    for event in events:
        if event.get("type") != event_type:
            continue
        if all(event.get(key) == value for key, value in match.items()):
            total += 1
    return total


def _claims(events: list[dict[str, Any]]) -> int:
    return sum(1 for event in events if event.get("type") == "claim" and event.get("attempt") is not None)


def _safe_adapter(adapter, method: str) -> dict[str, Any]:
    try:
        return getattr(adapter, method)()
    except Exception:
        return {}


def _base_result(
    *,
    scheme: str,
    scenario: str,
    repeat: int,
    job_id: int,
    run_id: str,
    started: float,
    published: float,
    fault_at: float,
    terminal_at: float | None,
    cleanup_at: float | None,
    snapshot: dict[str, Any],
    events: list[dict[str, Any]],
    adapter,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    deliveries = _count(events, "consumed")
    claims = _claims(events)
    acks = _count(events, "ack")
    scan = [event for event in events if event.get("type") == "recovery_scan"]
    result: dict[str, Any] = {
        "experiment_id": f"{run_id}:{scheme}:{scenario}:{repeat}",
        "scheme": scheme,
        "scenario": scenario,
        "repeat": repeat,
        "job_id": job_id,
        "run_id": run_id,
        "timings": {
            "published_s": round(published - started, 4),
            "fault_s": round(fault_at - started, 4),
            "terminal_s": round(terminal_at - started, 4) if terminal_at is not None else None,
            "cleanup_s": round(cleanup_at - started, 4) if cleanup_at is not None else None,
            "terminal_latency_s": round(terminal_at - fault_at, 4) if terminal_at is not None else None,
            "recovery_latency_s": round(cleanup_at - fault_at, 4) if cleanup_at is not None else None,
            "cleanup_latency_s": round(cleanup_at - fault_at, 4) if cleanup_at is not None else None,
            "elapsed_s": round(cleanup_at - started, 4) if cleanup_at is not None else None,
        },
        "counts": {
            "deliveries": deliveries,
            "claims": claims,
            "acks": acks,
            "redeliveries": max(0, deliveries - 1),
            "successful_business_executions": int(snapshot.get("audit_succeeded", 0)),
            "duplicate_business_executions": max(0, int(snapshot.get("audit_succeeded", 0)) - 1),
        },
        "scan": {
            "recovery_scans": len(scan),
            "db_scan_s": round(sum(float(item.get("db_scan_s", 0)) for item in scan), 4),
            "delivery_scan_s": round(sum(float(item.get("delivery_scan_s", 0)) for item in scan), 4),
            "stale_deliveries": sum(int(item.get("stale_count", 0)) for item in scan),
        },
        "delivery_sizes": _safe_adapter(adapter, "sizes"),
        "redis_memory": _safe_adapter(adapter, "memory"),
        "snapshot": snapshot,
        "events": events,
        "violations": [],
        "status": "FAIL",
    }
    if extra:
        result.update(extra)
    result["violations"] = _violations(result)
    result["status"] = "PASS" if not result["violations"] else "FAIL"
    return result


def _violations(result: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    scenario = result["scenario"]
    scheme = result["scheme"]
    snapshot = result["snapshot"]
    timings = result["timings"]
    counts = result["counts"]
    jobs = snapshot.get("jobs") or []
    if len(jobs) != 1:
        violations.append(f"expected one job row, found {len(jobs)}")
        return violations
    job = jobs[0]
    expected = "FAILED" if scenario == "max_attempts" else "SUCCEEDED"
    if job["status"] != expected:
        violations.append(f"final status {job['status']} != {expected}")
    if timings["terminal_s"] is None:
        violations.append("no terminal state before timeout")
    if timings["cleanup_s"] is None:
        violations.append("delivery channel was not clean before timeout")
    if counts["deliveries"] < 1:
        violations.append("no delivery observed")
    if counts["claims"] < 1:
        violations.append("no successful claim observed")
    if expected == "SUCCEEDED":
        if snapshot.get("audit_succeeded") != 1:
            violations.append(f"audit succeeded={snapshot.get('audit_succeeded')} != 1")
        if snapshot.get("audit_started", 0) < 1:
            violations.append("no quality_job.started audit event")
        if snapshot.get("issue_rows") != job["issue_count"]:
            violations.append(f"issue rows={snapshot.get('issue_rows')} != job issue_count={job['issue_count']}")
        if snapshot.get("duplicate_issue_groups"):
            violations.append("duplicate quality issue rows")
        outboxes = snapshot.get("outbox") or []
        if len(outboxes) != 1 or outboxes[0]["status"] != "DISPATCHED":
            violations.append(f"outbox state is not DISPATCHED: {outboxes}")
    else:
        if job.get("error_code") != "WORKER_LEASE_EXPIRED":
            violations.append(f"error_code={job.get('error_code')} != WORKER_LEASE_EXPIRED")
        if snapshot.get("audit_failed") != 1:
            violations.append(f"audit failed={snapshot.get('audit_failed')} != 1")
        if snapshot.get("audit_succeeded") != 0:
            violations.append("failed job produced a success audit")
    if counts["successful_business_executions"] != 1 and expected == "SUCCEEDED":
        violations.append("business success count != 1")
    if scenario == "duplicate_delivery":
        if counts["deliveries"] < 2:
            violations.append("duplicate delivery was not observed")
        if counts["claims"] != 1:
            violations.append(f"duplicate delivery caused {counts['claims']} claims")
    if scenario == "two_recoverers" and counts["claims"] > 2:
        violations.append(f"two recoverers produced {counts['claims']} claims")
    if scenario in {"after_db_before_ack", "after_ack_crash"} and scheme != "list" and counts["claims"] != 1:
        violations.append(f"ACK-window scenario produced {counts['claims']} claims")
    if scenario == "max_attempts" and counts["claims"] != 1:
        violations.append(f"exhausted job produced {counts['claims']} claims")
    return violations


def _publish(*, scheme: str, adapter, factory, job_ids: list[int], duplicates: int = 0) -> None:
    from benchmarks.queue_recovery.workload import mark_dispatched, reset_outbox_for_retry
    from server.admin.queue import dispatch_outbox

    if scheme == "list":
        reset_outbox_for_retry(factory, job_ids)
        for job_id in job_ids:
            result = dispatch_outbox(job_id=job_id, queue=adapter.queue)
            if result["published"] != 1:
                raise RuntimeError(f"outbox dispatch failed for job {job_id}: {result}")
        for _ in range(duplicates):
            for job_id in job_ids:
                adapter.publish(job_id)
        return
    mark_dispatched(factory, job_ids)
    for _ in range(1 + duplicates):
        for job_id in job_ids:
            adapter.publish(job_id)


def _recover_database(scheme: str = "list") -> dict[str, int]:
    from server.admin.worker import recover_worker_state

    orphaned = 2 if scheme == "list" else 10**9
    counts: dict[str, int] = {}
    # MySQL DATETIME has second precision. Retry the conditional scan briefly
    # so a lease that expired just after the previous scan is not lost.
    for _ in range(12):
        counts = recover_worker_state(stale_running_seconds=2, orphaned_seconds=orphaned, limit=100)
        if any(counts.values()):
            return counts
        time.sleep(0.5)
    return counts


def _recover_list(
    *,
    mysql_url: str,
    redis_url: str,
    run_id: str,
    adapter,
    event_dir: Path,
    worker_id: str = "recover",
    workers: int = 1,
) -> list[multiprocessing.Process]:
    processes: list[multiprocessing.Process] = []
    for index in range(workers):
        process = _start_worker(
            scheme="list",
            mysql_url=mysql_url,
            redis_url=redis_url,
            run_id=run_id,
            worker_id=f"{worker_id}-{index}",
            event_dir=event_dir,
            max_jobs=1,
            idle_seconds=8,
        )
        processes.append(process)
    _recover_database("list")
    return processes


def _recover_delivery(
    *,
    scheme: str,
    mysql_url: str,
    redis_url: str,
    run_id: str,
    event_dir: Path,
    worker_id: str = "recover",
    workers: int = 1,
) -> list[multiprocessing.Process]:
    processes: list[multiprocessing.Process] = []
    for index in range(workers):
        processes.append(
            _start_recovery(
                scheme=scheme,
                mysql_url=mysql_url,
                redis_url=redis_url,
                run_id=run_id,
                worker_id=f"{worker_id}-{index}",
                event_dir=event_dir,
            )
        )
    return processes


def _consume_ready(
    *,
    scheme: str,
    mysql_url: str,
    redis_url: str,
    run_id: str,
    event_dir: Path,
    worker_id: str = "consume-ready",
) -> multiprocessing.Process:
    process = _start_worker(
        scheme=scheme,
        mysql_url=mysql_url,
        redis_url=redis_url,
        run_id=run_id,
        worker_id=worker_id,
        event_dir=event_dir,
        max_jobs=1,
        idle_seconds=6,
    )
    _join(process, timeout=30)
    return process


def _fault_worker(
    *,
    scheme: str,
    mysql_url: str,
    redis_url: str,
    run_id: str,
    event_dir: Path,
    fault: str,
) -> tuple[multiprocessing.Process, float]:
    process = _start_worker(
        scheme=scheme,
        mysql_url=mysql_url,
        redis_url=redis_url,
        run_id=run_id,
        worker_id="fault",
        event_dir=event_dir,
        fault=fault,
        max_jobs=1,
    )
    try:
        event = _wait_marker(event_dir / f"{fault}.fault.json", timeout=20)
        fault_at = float(event["monotonic"])
    except Exception:
        _kill(process)
        raise
    from benchmarks.queue_recovery.worker import _append_event

    _append_event(str(event_dir), "parent", {"type": "parent_saw_fault", "monotonic": time.monotonic()})
    _kill(process)
    _append_event(str(event_dir), "parent", {"type": "parent_killed", "monotonic": time.monotonic()})
    return process, fault_at


def _run_fault_once(
    *,
    scheme: str,
    scenario: str,
    repeat: int,
    mysql_url: str,
    redis_url: str,
    redis_container: str,
    mysql_container: str,
) -> dict[str, Any]:
    from benchmarks.queue_recovery.adapters import make_adapter
    from benchmarks.queue_recovery.workload import create_jobs, prepare_database

    run_id = uuid.uuid4().hex
    event_dir = Path("/tmp") / f"gaobao-qr-{run_id}"
    event_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    engine, factory = prepare_database(mysql_url, schools=200, scores_per_school=5)
    adapter = make_adapter(scheme, redis_url, run_id=run_id, consumer=f"recover-{run_id[:8]}")
    processes: list[multiprocessing.Process] = []
    job_id: int | None = None
    try:
        job_id = create_jobs(factory, 1, max_attempts=1 if scenario == "max_attempts" else 3)[0]
        if scenario == "redis_unavailable":
            _publish(scheme=scheme, adapter=adapter, factory=factory, job_ids=[job_id])
            published = time.monotonic()
            fault_at = time.monotonic()
            _docker("pause", redis_container)
            process = _start_worker(
                scheme=scheme,
                mysql_url=mysql_url,
                redis_url=redis_url,
                run_id=run_id,
                worker_id="outage",
                event_dir=event_dir,
                max_jobs=1,
                config=SHORT_CONFIG,
                max_runtime=20,
            )
            processes.append(process)
            time.sleep(3.0)
            _docker("unpause", redis_container)
            _wait_redis_ready(redis_url)
            _join(process, timeout=15)
            snapshot, terminal_at, cleanup_at, pending = _wait_terminal(factory, adapter, job_id, timeout=20)
            if terminal_at is None:
                if scheme == "list":
                    processes.extend(
                        _recover_list(
                            mysql_url=mysql_url,
                            redis_url=redis_url,
                            run_id=run_id,
                            adapter=adapter,
                            event_dir=event_dir,
                        )
                    )
                else:
                    processes.extend(
                        _recover_delivery(
                            scheme=scheme,
                            mysql_url=mysql_url,
                            redis_url=redis_url,
                            run_id=run_id,
                            event_dir=event_dir,
                        )
                    )
                    process = _start_worker(
                        scheme=scheme,
                        mysql_url=mysql_url,
                        redis_url=redis_url,
                        run_id=run_id,
                        worker_id="post-outage",
                        event_dir=event_dir,
                        max_jobs=1,
                        idle_seconds=4,
                    )
                    processes.append(process)
                    _join(process, timeout=30)
                snapshot, terminal_at, cleanup_at, pending = _wait_terminal(factory, adapter, job_id, timeout=30)
        elif scenario == "mysql_unavailable":
            _publish(scheme=scheme, adapter=adapter, factory=factory, job_ids=[job_id])
            published = time.monotonic()
            fault_at = time.monotonic()
            _docker("pause", mysql_container)
            process = _start_worker(
                scheme=scheme,
                mysql_url=mysql_url,
                redis_url=redis_url,
                run_id=run_id,
                worker_id="outage",
                event_dir=event_dir,
                max_jobs=1,
                config=SHORT_CONFIG,
                max_runtime=20,
            )
            processes.append(process)
            time.sleep(3.0)
            _docker("unpause", mysql_container)
            _wait_mysql_ready(mysql_url, mysql_container)
            _join(process, timeout=15)
            snapshot, terminal_at, cleanup_at, pending = _wait_terminal(factory, adapter, job_id, timeout=10)
            if terminal_at is None:
                if scheme == "list":
                    processes.extend(
                        _recover_list(
                            mysql_url=mysql_url,
                            redis_url=redis_url,
                            run_id=run_id,
                            adapter=adapter,
                            event_dir=event_dir,
                        )
                    )
                else:
                    processes.extend(
                        _recover_delivery(
                            scheme=scheme,
                            mysql_url=mysql_url,
                            redis_url=redis_url,
                            run_id=run_id,
                            event_dir=event_dir,
                        )
                    )
                snapshot, terminal_at, cleanup_at, pending = _wait_terminal(factory, adapter, job_id, timeout=30)
        else:
            duplicates = 1 if scenario == "duplicate_delivery" else 0
            _publish(scheme=scheme, adapter=adapter, factory=factory, job_ids=[job_id], duplicates=duplicates)
            published = time.monotonic()
            if scenario == "published_not_consumed":
                _process, fault_at = _fault_worker(
                    scheme=scheme,
                    mysql_url=mysql_url,
                    redis_url=redis_url,
                    run_id=run_id,
                    event_dir=event_dir,
                    fault="before_consume",
                )
                process = _start_worker(
                    scheme=scheme,
                    mysql_url=mysql_url,
                    redis_url=redis_url,
                    run_id=run_id,
                    worker_id="normal",
                    event_dir=event_dir,
                    max_jobs=1,
                )
                processes.append(process)
                _join(process, timeout=30)
            elif scenario == "duplicate_delivery":
                process = _start_worker(
                    scheme=scheme,
                    mysql_url=mysql_url,
                    redis_url=redis_url,
                    run_id=run_id,
                    worker_id="duplicate",
                    event_dir=event_dir,
                    max_jobs=2,
                )
                processes.append(process)
                _join(process, timeout=30)
                fault_at = published
            elif scenario == "redis_restart":
                _process, fault_at = _fault_worker(
                    scheme=scheme,
                    mysql_url=mysql_url,
                    redis_url=redis_url,
                    run_id=run_id,
                    event_dir=event_dir,
                    fault="after_consume",
                )
                time.sleep(0.1)
                _save_adapter(adapter)
                _docker("restart", redis_container, timeout=60)
                _wait_redis_ready(redis_url)
                if scheme == "list":
                    processes.extend(
                        _recover_list(
                            mysql_url=mysql_url,
                            redis_url=redis_url,
                            run_id=run_id,
                            adapter=adapter,
                            event_dir=event_dir,
                        )
                    )
                else:
                    processes.extend(
                        _recover_delivery(
                            scheme=scheme,
                            mysql_url=mysql_url,
                            redis_url=redis_url,
                            run_id=run_id,
                            event_dir=event_dir,
                        )
                    )
                    process = _start_worker(
                        scheme=scheme,
                        mysql_url=mysql_url,
                        redis_url=redis_url,
                        run_id=run_id,
                        worker_id="post-restart",
                        event_dir=event_dir,
                        max_jobs=1,
                        idle_seconds=4,
                    )
                    processes.append(process)
                    _join(process, timeout=30)
            elif scenario == "after_ack_crash":
                _process, fault_at = _fault_worker(
                    scheme=scheme,
                    mysql_url=mysql_url,
                    redis_url=redis_url,
                    run_id=run_id,
                    event_dir=event_dir,
                    fault="after_ack_crash",
                )
                processes.extend(
                    _recover_delivery(
                        scheme=scheme,
                        mysql_url=mysql_url,
                        redis_url=redis_url,
                        run_id=run_id,
                        event_dir=event_dir,
                        worker_id="post-ack",
                    )
                )
            else:
                fault_by_scenario = {
                    "after_consume": "after_consume",
                    "after_claim": "after_claim",
                    "during_execute": "during_execute",
                    "after_db_before_ack": "after_db_before_ack",
                    "two_recoverers": "after_claim",
                    "max_attempts": "after_claim",
                }
                _process, fault_at = _fault_worker(
                    scheme=scheme,
                    mysql_url=mysql_url,
                    redis_url=redis_url,
                    run_id=run_id,
                    event_dir=event_dir,
                    fault=fault_by_scenario[scenario],
                )
                if scenario == "two_recoverers":
                    if scheme == "list":
                        processes.extend(
                            _recover_list(
                                mysql_url=mysql_url,
                                redis_url=redis_url,
                                run_id=run_id,
                                adapter=adapter,
                                event_dir=event_dir,
                                worker_id="recover",
                                workers=2,
                            )
                        )
                    else:
                        processes.extend(
                            _recover_delivery(
                                scheme=scheme,
                                mysql_url=mysql_url,
                                redis_url=redis_url,
                                run_id=run_id,
                                event_dir=event_dir,
                                worker_id="recover",
                                workers=2,
                            )
                        )
                elif scheme == "list":
                    processes.extend(
                        _recover_list(
                            mysql_url=mysql_url,
                            redis_url=redis_url,
                            run_id=run_id,
                            adapter=adapter,
                            event_dir=event_dir,
                        )
                    )
                else:
                    processes.extend(
                        _recover_delivery(
                            scheme=scheme,
                            mysql_url=mysql_url,
                            redis_url=redis_url,
                            run_id=run_id,
                            event_dir=event_dir,
                        )
                    )
            snapshot, terminal_at, cleanup_at, pending = _wait_terminal(factory, adapter, job_id, timeout=45)
        # Reconcile the transactional outbox after an alternative delivery
        # path recovered the job. A terminal job must not be left looking
        # undelivered merely because Streams/BLMOVE, not the List dispatcher,
        # performed the successful delivery.
        if scheme != "list" and snapshot.get("jobs") and snapshot["jobs"][0].get("status") == "SUCCEEDED":
            from benchmarks.queue_recovery.workload import mark_dispatched
            from benchmarks.queue_recovery.workload import snapshot as take_snapshot

            mark_dispatched(factory, [job_id])
            snapshot = take_snapshot(factory, [job_id])
        result = _base_result(
            scheme=scheme,
            scenario=scenario,
            repeat=repeat,
            job_id=job_id,
            run_id=run_id,
            started=started,
            published=float(published),
            fault_at=float(fault_at),
            terminal_at=terminal_at,
            cleanup_at=cleanup_at,
            snapshot=snapshot,
            events=_events(event_dir),
            adapter=adapter,
            extra={"pending_at_end": pending, "short_lease_config": SHORT_CONFIG},
        )
        return result
    finally:
        for process in processes:
            _kill(process)
        adapter.close()
        engine.dispose()


def _run_default_once(
    *,
    mysql_url: str,
    redis_url: str,
    repeat: int,
) -> dict[str, Any]:
    from benchmarks.queue_recovery.adapters import make_adapter
    from benchmarks.queue_recovery.workload import create_jobs, prepare_database

    run_id = uuid.uuid4().hex
    event_dir = Path("/tmp") / f"gaobao-qr-default-{run_id}"
    event_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    engine, factory = prepare_database(mysql_url, schools=200, scores_per_school=5)
    adapter = make_adapter("list", redis_url, run_id=run_id)
    processes: list[multiprocessing.Process] = []
    try:
        job_id = create_jobs(factory, 1)[0]
        _publish(scheme="list", adapter=adapter, factory=factory, job_ids=[job_id])
        published = time.monotonic()
        _process, fault_at = _fault_worker(
            scheme="list",
            mysql_url=mysql_url,
            redis_url=redis_url,
            run_id=run_id,
            event_dir=event_dir,
            fault="after_consume",
        )
        process = _start_production_worker(
            mysql_url=mysql_url,
            redis_url=redis_url,
            run_id=run_id,
            event_dir=event_dir,
            worker_id="production",
            queue_key=adapter.queue.key,
            max_runtime=180,
        )
        processes.append(process)
        snapshot, terminal_at, cleanup_at, pending = _wait_terminal(
            factory, adapter, job_id, timeout=150, require_cleanup=True
        )
        _terminate(process)
        result = _base_result(
            scheme="list",
            scenario="default_60_30_after_consume",
            repeat=repeat,
            job_id=job_id,
            run_id=run_id,
            started=started,
            published=published,
            fault_at=fault_at,
            terminal_at=terminal_at,
            cleanup_at=cleanup_at,
            snapshot=snapshot,
            events=_events(event_dir),
            adapter=adapter,
            extra={
                "production_config": DEFAULT_CONFIG,
                "recovery_definition": (
                    "fault marker to terminal DB state and empty queue; production worker startup scan "
                    "plus 30s periodic scan, 60s delivery lease"
                ),
                "pending_at_end": pending,
            },
        )
        return result
    finally:
        for process in processes:
            _kill(process)
        adapter.close()
        engine.dispose()


def _run_load_once(
    *,
    scheme: str,
    mysql_url: str,
    redis_url: str,
    jobs: int,
    workers: int,
    repeat: int,
    containers: list[str],
) -> dict[str, Any]:
    from benchmarks.queue_recovery.adapters import make_adapter
    from benchmarks.queue_recovery.metrics import ResourceSampler
    from benchmarks.queue_recovery.workload import create_jobs, prepare_database, snapshot

    run_id = uuid.uuid4().hex
    event_dir = Path("/tmp") / f"gaobao-qr-load-{run_id}"
    event_dir.mkdir(parents=True, exist_ok=True)
    engine, factory = prepare_database(mysql_url, schools=200, scores_per_school=5)
    adapter = make_adapter(scheme, redis_url, run_id=run_id)
    processes: list[multiprocessing.Process] = []
    sampler: ResourceSampler | None = None
    try:
        job_ids = create_jobs(factory, jobs, prefix="load")
        _publish(scheme=scheme, adapter=adapter, factory=factory, job_ids=job_ids)
        published = time.monotonic()
        for index in range(workers):
            processes.append(
                _start_worker(
                    scheme=scheme,
                    mysql_url=mysql_url,
                    redis_url=redis_url,
                    run_id=run_id,
                    worker_id=f"load-{index}",
                    event_dir=event_dir,
                    max_jobs=0,
                    idle_seconds=3,
                    max_runtime=150,
                )
            )
        sampler = ResourceSampler(
            containers=containers,
            pids=lambda: [process.pid for process in processes if process.is_alive()],
            interval=1.0,
        )
        sampler.start()
        deadline = time.monotonic() + 180
        final: dict[str, Any] = {}
        while time.monotonic() < deadline:
            final = snapshot(factory, job_ids)
            if all(item["status"] in {"SUCCEEDED", "FAILED"} for item in final["jobs"]):
                break
            time.sleep(0.1)
        ended = time.monotonic()
        sampler.stop()
        resources = sampler.summary()
        sizes = adapter.sizes()
        memory = adapter.memory()
        for process in processes:
            _join(process, timeout=10)
        events = _events(event_dir)
        executions = [event for event in events if event.get("type") == "execution"]
        deliveries = _count(events, "consumed")
        claims = _claims(events)
        succeeded = sum(1 for item in final["jobs"] if item["status"] == "SUCCEEDED")
        failed = sum(1 for item in final["jobs"] if item["status"] == "FAILED")
        queue_wait = [float(item["started_monotonic"]) - published for item in executions]
        execution_time = [float(item["finished_monotonic"]) - float(item["started_monotonic"]) for item in executions]
        end_to_end = [float(item["finished_monotonic"]) - published for item in executions]
        issue_sum = sum(int(item["issue_count"]) for item in final["jobs"])
        violations: list[str] = []
        if len(final.get("jobs") or []) != jobs:
            violations.append(f"job rows={len(final.get('jobs') or [])} != {jobs}")
        if succeeded != jobs:
            violations.append(f"succeeded={succeeded} != {jobs}")
        if failed:
            violations.append(f"failed={failed}")
        if final.get("audit_succeeded") != jobs:
            violations.append(f"audit_succeeded={final.get('audit_succeeded')} != {jobs}")
        if final.get("audit_started") != jobs:
            violations.append(f"audit_started={final.get('audit_started')} != {jobs}")
        if final.get("issue_rows") != issue_sum:
            violations.append("issue rows do not match job issue counts")
        if final.get("duplicate_issue_groups"):
            violations.append("duplicate quality issue rows")
        if claims != jobs:
            violations.append(f"claims={claims} != {jobs}")
        if deliveries < jobs:
            violations.append(f"deliveries={deliveries} < {jobs}")
        result = {
            "experiment_id": f"{run_id}:{scheme}:load:{jobs}:{workers}:{repeat}",
            "scheme": scheme,
            "scenario": "load",
            "repeat": repeat,
            "jobs": jobs,
            "workers": workers,
            "run_id": run_id,
            "wall_s": round(ended - published, 4),
            "jobs_per_s": round(succeeded / (ended - published), 3) if ended > published else 0.0,
            "counts": {
                "succeeded": succeeded,
                "failed": failed,
                "deliveries": deliveries,
                "claims": claims,
                "redeliveries": max(0, deliveries - jobs),
                "redelivery_rate": round(max(0, deliveries - jobs) / jobs, 4) if jobs else 0.0,
                "duplicate_business_executions": max(0, int(final.get("audit_succeeded", 0)) - jobs),
            },
            "error_rate": round(failed / jobs, 4) if jobs else 0.0,
            "queue_wait": summarize(queue_wait),
            "execution": summarize(execution_time),
            "end_to_end": summarize(end_to_end),
            "audit": {
                "created": final.get("audit_created"),
                "started": final.get("audit_started"),
                "succeeded": final.get("audit_succeeded"),
                "failed": final.get("audit_failed"),
                "retry": final.get("audit_retry"),
            },
            "issue_rows": final.get("issue_rows"),
            "delivery_sizes": sizes,
            "redis_memory": memory,
            "resources": resources,
            "endpoint_resources": docker_stats(containers),
            "snapshot": final,
            "events": events,
            "violations": violations,
            "status": "PASS" if not violations else "FAIL",
        }
        return result
    finally:
        if sampler is not None:
            sampler.stop()
        for process in processes:
            _kill(process)
        adapter.close()
        engine.dispose()


def _environment(mysql_url: str, redis_url: str, mysql_container: str, redis_container: str) -> dict[str, Any]:
    import platform

    def _version(args: list[str]) -> str:
        try:
            return _docker(*args).stdout.strip().splitlines()[0]
        except Exception:
            return "unknown"

    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "mysql": _database_identity(mysql_url),
        "mysql_version": _version(["exec", mysql_container, "mysql", "--version"]),
        "redis_version": _version(["exec", redis_container, "redis-server", "--version"]),
        "redis_key_prefix": "gaobao:qr",
        "short_lease_config": SHORT_CONFIG,
        "production_defaults": DEFAULT_CONFIG,
        "production_default_note": (
            "Production defaults are validated separately with the real worker loop; "
            "fault scenarios use shortened leases and are not production defaults."
        ),
        "redis_url_scheme": urlsplit(redis_url).scheme,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def _summarize_output(output: dict[str, Any]) -> None:
    summary: dict[str, Any] = {"faults": {}, "loads": {}, "defaults": {}}
    for scheme in SCHEMES:
        rows = [row for row in output["faults"] if row.get("scheme") == scheme and row.get("status") == "PASS"]
        recovery = [
            float(row["timings"]["recovery_latency_s"])
            for row in rows
            if row.get("timings", {}).get("recovery_latency_s") is not None
        ]
        summary["faults"][scheme] = {
            "runs": len([row for row in output["faults"] if row.get("scheme") == scheme]),
            "passed": len(rows),
            "failed": len(
                [row for row in output["faults"] if row.get("scheme") == scheme and row.get("status") == "FAIL"]
            ),
            "not_run": len(
                [row for row in output["faults"] if row.get("scheme") == scheme and row.get("status") == "NOT_RUN"]
            ),
            "recovery": summarize(recovery),
            "redeliveries": sum(int(row.get("counts", {}).get("redeliveries", 0)) for row in rows),
            "duplicate_business_executions": sum(
                int(row.get("counts", {}).get("duplicate_business_executions", 0)) for row in rows
            ),
        }
        loads = [row for row in output["load"] if row.get("scheme") == scheme]
        summary["loads"][scheme] = {
            "runs": len(loads),
            "jobs_per_s": summarize([float(row["jobs_per_s"]) for row in loads if row.get("status") == "PASS"]),
            "queue_wait": summarize(
                [
                    float(row["queue_wait"]["p50"])
                    for row in loads
                    if row.get("status") == "PASS" and row.get("queue_wait", {}).get("samples")
                ]
            ),
            "end_to_end_p95": summarize(
                [
                    float(row["end_to_end"]["p95"])
                    for row in loads
                    if row.get("status") == "PASS" and row.get("end_to_end", {}).get("samples")
                ]
            ),
        }
    defaults = [row for row in output["defaults"] if row.get("status") == "PASS"]
    summary["defaults"]["list_60_30"] = {
        "runs": len(output["defaults"]),
        "recovery": summarize(
            [
                float(row["timings"]["recovery_latency_s"])
                for row in defaults
                if row.get("timings", {}).get("recovery_latency_s") is not None
            ]
        ),
    }
    output["summary"] = summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Redis queue recovery comparison")
    parser.add_argument("--mysql-url", default=os.getenv("MYSQL_BENCH_URL", "").strip())
    parser.add_argument("--redis-url", default=os.getenv("REDIS_BENCH_URL", "").strip())
    parser.add_argument("--suite", choices=["fault", "load", "default", "all"], default="all")
    parser.add_argument("--schemes", nargs="+", default=list(SCHEMES), choices=SCHEMES)
    parser.add_argument("--scenarios", nargs="+", default=list(SCENARIOS), choices=SCENARIOS)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--load-repeats", type=int, default=3)
    parser.add_argument("--default-repeats", type=int, default=3)
    parser.add_argument("--redis-container", default=os.getenv("REDIS_CONTAINER", "gaobao-qr-redis-1"))
    parser.add_argument("--mysql-container", default=os.getenv("MYSQL_CONTAINER", "gaobao-qr-mysql-1"))
    parser.add_argument("--containers", nargs="+", default=None)
    parser.add_argument("--json-out", default="")
    args = parser.parse_args(argv)
    if not args.mysql_url or not args.redis_url:
        parser.error("--mysql-url/--redis-url or MYSQL_BENCH_URL/REDIS_BENCH_URL are required")
    _set_environment(args.mysql_url, args.redis_url)
    containers = args.containers or [args.mysql_container, args.redis_container]
    output_path = Path(args.json_out) if args.json_out else None
    output: dict[str, Any] = {
        "environment": _environment(args.mysql_url, args.redis_url, args.mysql_container, args.redis_container),
        "faults": [],
        "load": [],
        "defaults": [],
        "summary": {},
    }

    def _flush() -> None:
        if output_path is None:
            return
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    if args.suite in {"fault", "all"}:
        for scheme in args.schemes:
            for scenario in args.scenarios:
                if scheme == "list" and scenario in LIST_NOT_APPLICABLE:
                    row = {
                        "scheme": scheme,
                        "scenario": scenario,
                        "status": "NOT_RUN",
                        "reason": "Redis List + BRPOP has no explicit ACK window; DB commit is the acknowledgement boundary",
                    }
                    output["faults"].append(row)
                    print(json.dumps({"scheme": scheme, "scenario": scenario, "status": "NOT_RUN"}))
                    _flush()
                    continue
                for repeat in range(args.repeats):
                    try:
                        result = _run_fault_once(
                            scheme=scheme,
                            scenario=scenario,
                            repeat=repeat,
                            mysql_url=args.mysql_url,
                            redis_url=args.redis_url,
                            redis_container=args.redis_container,
                            mysql_container=args.mysql_container,
                        )
                    except Exception as exc:  # noqa: BLE001 - record experiment failure
                        result = {
                            "scheme": scheme,
                            "scenario": scenario,
                            "repeat": repeat,
                            "status": "FAIL",
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    output["faults"].append(result)
                    print(
                        json.dumps(
                            {
                                "scheme": scheme,
                                "scenario": scenario,
                                "repeat": repeat,
                                "status": result.get("status"),
                                "recovery_s": result.get("timings", {}).get("recovery_latency_s"),
                                "violations": result.get("violations"),
                            }
                        )
                    )
                    _flush()
    if args.suite in {"load", "all"}:
        for scheme in args.schemes:
            for jobs, workers in ((20, 1), (50, 2), (100, 4)):
                for repeat in range(args.load_repeats):
                    try:
                        result = _run_load_once(
                            scheme=scheme,
                            mysql_url=args.mysql_url,
                            redis_url=args.redis_url,
                            jobs=jobs,
                            workers=workers,
                            repeat=repeat,
                            containers=containers,
                        )
                    except Exception as exc:  # noqa: BLE001
                        result = {
                            "scheme": scheme,
                            "scenario": "load",
                            "jobs": jobs,
                            "workers": workers,
                            "repeat": repeat,
                            "status": "FAIL",
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    output["load"].append(result)
                    print(
                        json.dumps(
                            {
                                "scheme": scheme,
                                "jobs": jobs,
                                "workers": workers,
                                "repeat": repeat,
                                "status": result.get("status"),
                                "jobs_per_s": result.get("jobs_per_s"),
                                "violations": result.get("violations"),
                            }
                        )
                    )
                    _flush()
    if args.suite in {"default", "all"}:
        for repeat in range(args.default_repeats):
            try:
                result = _run_default_once(
                    mysql_url=args.mysql_url,
                    redis_url=args.redis_url,
                    repeat=repeat,
                )
            except Exception as exc:  # noqa: BLE001
                result = {
                    "scheme": "list",
                    "scenario": "default_60_30_after_consume",
                    "repeat": repeat,
                    "status": "FAIL",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            output["defaults"].append(result)
            print(
                json.dumps(
                    {
                        "scheme": "list",
                        "scenario": "default_60_30_after_consume",
                        "repeat": repeat,
                        "status": result.get("status"),
                        "recovery_s": result.get("timings", {}).get("recovery_latency_s"),
                    }
                )
            )
            _flush()
    _summarize_output(output)
    text = json.dumps(output, ensure_ascii=False, indent=2, default=str)
    if output_path is None:
        print(text)
    else:
        _flush()
        print(f"wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
