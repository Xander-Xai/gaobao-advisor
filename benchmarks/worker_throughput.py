"""Measure real MySQL + Redis worker throughput for 1/2/4 worker processes.

Synthetic data only; the MySQL database is protected by benchmarks.guard.
Each scenario creates N quality jobs, dispatches them to a dedicated Redis
queue, runs W worker processes, and measures actual terminal DB state.

Example::

    MYSQL_BENCH_URL='mysql+pymysql://root:testroot@127.0.0.1:3307/gaobao_benchmark?charset=utf8mb4' \
    REDIS_BENCH_URL='redis://127.0.0.1:6380/0' \
      python -m benchmarks.worker_throughput --workers 1 2 4 --jobs 50
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import time
import uuid
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from benchmarks.guard import ensure_benchmark_database


def _worker_loop(queue_key: str, idle_seconds: int) -> None:
    from server.admin.queue import RedisQueue
    from server.admin.worker import run_once

    queue = RedisQueue(key=queue_key)
    idle = 0
    while idle < idle_seconds:
        try:
            result = run_once(queue=queue, timeout=1)
        except Exception:
            break
        if result.get("job_id"):
            idle = 0
        else:
            idle += 1
    queue.close()


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round((len(ordered) - 1) * 0.95)))]


def _run_scenario(*, mysql_url: str, redis_url: str, workers: int, jobs: int, schools: int, scores: int) -> dict:
    engine = create_engine(mysql_url, pool_pre_ping=True, pool_recycle=1800)
    ensure_benchmark_database(engine, mysql_url, allow_database_url_match=True)
    os.environ["DATABASE_URL"] = mysql_url
    os.environ["REDIS_URL"] = redis_url
    os.environ["QUALITY_TASK_MODE"] = "async"

    import db.models  # noqa: F401
    from db.database import Base
    from db.models import DataQualityJob
    from scripts.benchmark_admin_queries import PROVINCES, build_dataset
    from server.admin import repository
    from server.admin.queue import RedisQueue, dispatch_outbox

    with engine.begin() as connection:
        connection.execute(text("SET FOREIGN_KEY_CHECKS=0"))
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = factory()
    try:
        build_dataset(session, schools, scores)
    finally:
        session.close()

    queue_key = f"gaobao:bench:worker:{uuid.uuid4().hex}"
    queue = RedisQueue(url=redis_url, key=queue_key)
    if not queue.ping():
        engine.dispose()
        raise RuntimeError("Redis benchmark queue is unreachable")

    session = factory()
    try:
        ids = []
        for index in range(jobs):
            job, _ = repository.create_job_with_outbox(
                session,
                filters={"province": PROVINCES[index % len(PROVINCES)]},
                idempotency_key=f"bench-worker-{uuid.uuid4().hex}",
                actor="benchmark",
                role="operator",
                request_id=f"bench-{index}",
                ip_hash=None,
            )
            ids.append(job.id)
        for job_id in ids:
            dispatch_outbox(job_id=job_id, queue=queue)
    finally:
        session.close()

    started = time.perf_counter()
    ctx = multiprocessing.get_context("fork")
    processes = [ctx.Process(target=_worker_loop, args=(queue_key, 3), daemon=True) for _ in range(workers)]
    for process in processes:
        process.start()

    deadline = time.monotonic() + 300
    terminal = 0
    while time.monotonic() < deadline:
        session = factory()
        try:
            terminal = (
                session.query(DataQualityJob)
                .filter(DataQualityJob.id.in_(ids), DataQualityJob.status.in_(("SUCCEEDED", "FAILED")))
                .count()
            )
        finally:
            session.close()
        if terminal >= jobs:
            break
        time.sleep(0.2)
    elapsed = time.perf_counter() - started
    for process in processes:
        process.join(timeout=5)
        if process.is_alive():
            process.terminate()

    session = factory()
    try:
        rows = session.query(DataQualityJob).filter(DataQualityJob.id.in_(ids)).all()
        waits = [(row.started_at - row.created_at).total_seconds() for row in rows if row.started_at and row.created_at]
        executions = [
            (row.finished_at - row.started_at).total_seconds() for row in rows if row.finished_at and row.started_at
        ]
        end_to_end = [
            (row.finished_at - row.created_at).total_seconds() for row in rows if row.finished_at and row.created_at
        ]
        succeeded = sum(1 for row in rows if row.status == "SUCCEEDED")
        failed = sum(1 for row in rows if row.status == "FAILED")
        retries = sum(1 for row in rows if row.attempts > 1)
        with engine.connect() as connection:
            connections = connection.execute(text("SHOW STATUS LIKE 'Threads_connected'")).one()[1]
    finally:
        session.close()
        queue.close()
        engine.dispose()

    return {
        "workers": workers,
        "jobs": jobs,
        "completed": terminal,
        "succeeded": succeeded,
        "failed": failed,
        "retries": retries,
        "elapsed_s": round(elapsed, 3),
        "jobs_per_s": round(terminal / elapsed, 3) if elapsed else 0.0,
        "queue_wait_p95_s": round(_p95(waits), 3),
        "execution_p95_s": round(_p95(executions), 3),
        "end_to_end_p95_s": round(_p95(end_to_end), 3),
        "error_rate": round(failed / len(rows), 4) if rows else 0.0,
        "db_threads_connected": connections,
        "timestamp_precision_note": "MySQL DATETIME is second precision; wait/exec p95 are coarse",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MySQL + Redis worker throughput benchmark")
    parser.add_argument("--mysql-url", default=os.getenv("MYSQL_BENCH_URL", "").strip())
    parser.add_argument("--redis-url", default=os.getenv("REDIS_BENCH_URL", "").strip())
    parser.add_argument("--workers", type=int, nargs="+", default=[1, 2, 4])
    parser.add_argument("--jobs", type=int, default=50)
    parser.add_argument("--schools", type=int, default=500)
    parser.add_argument("--scores-per-school", type=int, default=5)
    parser.add_argument("--json-out", default="")
    args = parser.parse_args(argv)
    if not args.mysql_url or not args.redis_url:
        parser.error("--mysql-url/--redis-url or MYSQL_BENCH_URL/REDIS_BENCH_URL are required")
    results = []
    for workers in args.workers:
        results.append(
            _run_scenario(
                mysql_url=args.mysql_url,
                redis_url=args.redis_url,
                workers=workers,
                jobs=args.jobs,
                schools=args.schools,
                scores=args.scores_per_school,
            )
        )
    output = {"scenarios": results}
    text_result = json.dumps(output, ensure_ascii=False, indent=2, default=str)
    print(text_result)
    if args.json_out:
        path = Path(args.json_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text_result + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
