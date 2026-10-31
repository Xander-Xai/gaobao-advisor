"""Reproducible MySQL 8.4 administrator query benchmark.

Synthetic data only. The target database must be dedicated and is protected by
``benchmarks.guard``. This measures SQL/repository latency, not production SLA.

Example::

    MYSQL_BENCH_URL='mysql+pymysql://root:testroot@127.0.0.1:3307/gaobao_benchmark?charset=utf8mb4' \
      python -m benchmarks.mysql_admin_benchmark \
        --schools 2000 --scores-per-school 5 --audit-rows 50000 --job-rows 2000 \
        --concurrency 10 --warmup 10 --repeat 50 --json-out /tmp/bench.json
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import statistics
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

import db.models  # noqa: F401 - register metadata
from benchmarks.guard import ensure_benchmark_database
from db.database import Base
from db.models import DataQualityJob, OperationAuditLog
from scripts.benchmark_admin_queries import PROVINCES, build_dataset
from server.admin import repository
from server.admin.quality import collect_issues

BENCH_SCHOOL_QUERY = "SELECT id, name, province, city, level, school_type, ranking FROM schools ORDER BY id LIMIT 20"
AUDIT_SQL = "SELECT * FROM operation_audit_logs ORDER BY created_at DESC, id DESC LIMIT 20"
JOBS_SQL = "SELECT * FROM data_quality_jobs ORDER BY created_at DESC, id DESC LIMIT 20"


def _now_minus(seconds: int) -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(seconds=seconds)


def _reset_schema(engine) -> None:
    with engine.begin() as connection:
        connection.execute(text("SET FOREIGN_KEY_CHECKS=0"))
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("SET FOREIGN_KEY_CHECKS=1"))


def _populate(session: Session, schools: int, scores_per_school: int, audit_rows: int, job_rows: int) -> None:
    build_dataset(session, schools, scores_per_school)
    if audit_rows:
        session.bulk_insert_mappings(
            OperationAuditLog,
            [
                {
                    "request_id": f"bench-{i}",
                    "actor": "benchmark",
                    "role": "operator",
                    "action": "benchmark.audit",
                    "resource_type": "benchmark",
                    "resource_id": str(i),
                    "outcome": "SUCCESS",
                    "detail_json": "{}",
                    "created_at": _now_minus(i),
                }
                for i in range(audit_rows)
            ],
        )
    if job_rows:
        session.bulk_insert_mappings(
            DataQualityJob,
            [
                {
                    "job_type": "admission_data_quality",
                    "status": "SUCCEEDED",
                    "review_status": "PENDING_REVIEW",
                    "idempotency_key": f"bench-job-{i}",
                    "filters_json": "{}",
                    "requested_by": "benchmark",
                    "execution_mode": "async",
                    "source_marker": "SYNTHETIC_DEMO_DATA",
                    "attempts": 1,
                    "max_attempts": 3,
                    "version": 2,
                    "checked_rows": 10,
                    "issue_count": 0,
                    "created_at": _now_minus(i),
                    "updated_at": _now_minus(i),
                    "finished_at": _now_minus(i),
                }
                for i in range(job_rows)
            ],
        )
    session.commit()


def _stats(samples: list[float]) -> dict[str, float]:
    ordered = sorted(samples)
    count = len(ordered)

    def pct(p: float) -> float:
        return ordered[min(count - 1, max(0, int(round((count - 1) * p))))]

    mean = statistics.fmean(ordered)
    return {
        "samples": count,
        "p50_ms": round(pct(0.50), 3),
        "p95_ms": round(pct(0.95), 3),
        "p99_ms": round(pct(0.99), 3),
        "mean_ms": round(mean, 3),
        "min_ms": round(ordered[0], 3),
        "max_ms": round(ordered[-1], 3),
        "throughput_per_s": round(1000 / mean, 2) if mean else 0.0,
    }


def _measure(fn: Callable[[], Any], *, warmup: int, repeat: int) -> dict[str, float]:
    for _ in range(warmup):
        fn()
    samples = []
    for _ in range(repeat):
        started = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - started) * 1000)
    return _stats(samples)


def _measure_concurrent(factory, fn: Callable[[Session], Any], *, concurrency: int, iterations: int) -> dict[str, Any]:
    from concurrent.futures import ThreadPoolExecutor

    def one(_index: int) -> tuple[float, bool]:
        session = factory()
        started = time.perf_counter()
        try:
            fn(session)
            return (time.perf_counter() - started) * 1000, True
        except Exception:
            return (time.perf_counter() - started) * 1000, False
        finally:
            session.close()

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(one, range(iterations)))
    elapsed = time.perf_counter() - started
    samples = [item[0] for item in results]
    stats = _stats(samples)
    stats.update(
        {
            "concurrency": concurrency,
            "iterations": iterations,
            "errors": sum(1 for _latency, ok in results if not ok),
            "error_rate": round(sum(1 for _latency, ok in results if not ok) / len(results), 4),
            "wall_throughput_per_s": round(len(results) / elapsed, 2) if elapsed else 0.0,
        }
    )
    return stats


def _explain(engine, sql: str) -> list[str]:
    with engine.connect() as connection:
        rows = connection.execute(text(f"EXPLAIN ANALYZE {sql}")).all()
    return [str(row[0]) for row in rows]


def _index_exists(engine, table: str, name: str) -> bool:
    return any(index["name"] == name for index in inspect(engine).get_indexes(table))


def _drop_index(engine, table: str, name: str) -> None:
    if _index_exists(engine, table, name):
        with engine.begin() as connection:
            connection.execute(text(f"DROP INDEX {name} ON {table}"))


def _create_index(engine, table: str, name: str, column: str) -> None:
    if not _index_exists(engine, table, name):
        with engine.begin() as connection:
            connection.execute(text(f"CREATE INDEX {name} ON {table} ({column})"))


def _environment(engine) -> dict[str, Any]:
    with engine.connect() as connection:
        mysql_version = connection.execute(text("SELECT VERSION()")).scalar_one()
    cpu_model = "unknown"
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.lower().startswith("model name"):
                cpu_model = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    memory = "unknown"
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                memory = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    try:
        git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, timeout=5).strip()
    except Exception:
        git_sha = "unknown"
    return {
        "git_sha": git_sha,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "mysql": mysql_version,
        "cpu": cpu_model,
        "cpu_count": os.cpu_count(),
        "ram": memory,
    }


def run(args) -> dict[str, Any]:
    engine = create_engine(args.mysql_url, pool_pre_ping=True, pool_recycle=1800)
    ensure_benchmark_database(engine, args.mysql_url)
    _reset_schema(engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = factory()
    try:
        _populate(session, args.schools, args.scores_per_school, args.audit_rows, args.job_rows)
        school_id = session.execute(text("SELECT MIN(id) FROM schools")).scalar_one()

        def list_schools(filters=None, sort="id", order="asc", page=1):
            return repository.list_schools(
                session,
                filters=filters or {},
                sort=sort,
                order=order,
                page=page,
                page_size=20,
            )

        workloads = {
            "schools_page_1": _measure(lambda: list_schools(), warmup=args.warmup, repeat=args.repeat),
            "schools_deep_page": _measure(
                lambda: list_schools(page=max(1, args.schools // 20)), warmup=args.warmup, repeat=args.repeat
            ),
            "schools_filter_province": _measure(
                lambda: list_schools(filters={"province": PROVINCES[0]}, sort="name"),
                warmup=args.warmup,
                repeat=args.repeat,
            ),
            "schools_filter_sort": _measure(
                lambda: list_schools(filters={"province": PROVINCES[0], "level": "985"}, sort="ranking", order="desc"),
                warmup=args.warmup,
                repeat=args.repeat,
            ),
            "school_detail": _measure(
                lambda: repository.get_school_detail(session, school_id),
                warmup=args.warmup,
                repeat=args.repeat,
            ),
            "stats": _measure(lambda: repository.get_stats(session), warmup=args.warmup, repeat=args.repeat),
            "quality_scan_province": _measure(
                lambda: collect_issues(session, {"province": PROVINCES[0]}),
                warmup=max(1, args.warmup // 2),
                repeat=max(3, args.repeat // 5),
            ),
            "jobs_page_1": _measure(
                lambda: repository.list_jobs(session, status=None, review_status=None, page=1, page_size=20),
                warmup=args.warmup,
                repeat=args.repeat,
            ),
            "audit_page_1": _measure(
                lambda: repository.list_audit_logs(session, action=None, actor=None, page=1, page_size=20),
                warmup=args.warmup,
                repeat=args.repeat,
            ),
            "audit_deep_page": _measure(
                lambda: repository.list_audit_logs(
                    session, action=None, actor=None, page=min(1000, max(1, args.audit_rows // 20)), page_size=20
                ),
                warmup=args.warmup,
                repeat=args.repeat,
            ),
        }
        concurrent = _measure_concurrent(
            factory,
            lambda s: repository.list_schools(s, filters={}, sort="id", order="asc", page=1, page_size=20),
            concurrency=args.concurrency,
            iterations=max(args.concurrency * 5, 20),
        )

        # Index experiment: both indexes are additive; drop them to establish
        # Before on the same data, then create and measure After.
        index_experiment: dict[str, Any] = {}
        if not args.skip_index_experiment:
            # The measurement session has an open SELECT transaction. Release
            # it before DDL, otherwise MySQL metadata locks can block CREATE/
            # DROP INDEX indefinitely.
            session.commit()
            _drop_index(engine, "operation_audit_logs", "ix_audit_created")
            before = {
                "audit_page_1": _measure(
                    lambda: repository.list_audit_logs(session, action=None, actor=None, page=1, page_size=20),
                    warmup=args.warmup,
                    repeat=args.repeat,
                ),
                "audit_deep_page": _measure(
                    lambda: repository.list_audit_logs(
                        session, action=None, actor=None, page=min(1000, max(1, args.audit_rows // 20)), page_size=20
                    ),
                    warmup=args.warmup,
                    repeat=args.repeat,
                ),
                "audit_plan": _explain(engine, AUDIT_SQL),
            }
            session.commit()
            _create_index(engine, "operation_audit_logs", "ix_audit_created", "created_at")
            after = {
                "audit_page_1": _measure(
                    lambda: repository.list_audit_logs(session, action=None, actor=None, page=1, page_size=20),
                    warmup=args.warmup,
                    repeat=args.repeat,
                ),
                "audit_deep_page": _measure(
                    lambda: repository.list_audit_logs(
                        session, action=None, actor=None, page=min(1000, max(1, args.audit_rows // 20)), page_size=20
                    ),
                    warmup=args.warmup,
                    repeat=args.repeat,
                ),
                "audit_plan": _explain(engine, AUDIT_SQL),
            }
            index_experiment = {
                "before": before,
                "after": after,
                "optimization": "single-column audit created_at index for unfiltered audit pagination",
                "not_adopted": "data_quality_jobs created_at index was not used by MySQL 8.4 for this query shape",
            }

        result = {
            "environment": _environment(engine),
            "dataset": {
                "schools": args.schools,
                "scores_per_school": args.scores_per_school,
                "audit_rows": args.audit_rows,
                "job_rows": args.job_rows,
            },
            "method": {
                "warmup": args.warmup,
                "repeat": args.repeat,
                "concurrency": args.concurrency,
                "measurement": "SQLAlchemy repository latency (ms); no HTTP layer",
            },
            "workloads": workloads,
            "concurrency": concurrent,
            "index_experiment": index_experiment,
            "query_plans": {
                "schools": _explain(engine, BENCH_SCHOOL_QUERY),
                "audit": _explain(engine, AUDIT_SQL),
                "jobs": _explain(engine, JOBS_SQL),
            },
        }
    finally:
        session.close()
        engine.dispose()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MySQL 8.4 admin query benchmark")
    parser.add_argument("--mysql-url", default=os.getenv("MYSQL_BENCH_URL", "").strip())
    parser.add_argument("--schools", type=int, default=2000)
    parser.add_argument("--scores-per-school", type=int, default=5)
    parser.add_argument("--audit-rows", type=int, default=50_000)
    parser.add_argument("--job-rows", type=int, default=2_000)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--repeat", type=int, default=50)
    parser.add_argument("--skip-index-experiment", action="store_true")
    parser.add_argument("--json-out", default="")
    args = parser.parse_args(argv)
    if not args.mysql_url:
        parser.error("--mysql-url or MYSQL_BENCH_URL is required")
    result = run(args)
    text_result = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    print(text_result)
    if args.json_out:
        path = Path(args.json_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text_result + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
