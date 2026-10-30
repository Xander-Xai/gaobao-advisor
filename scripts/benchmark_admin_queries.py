"""Reproducible SQLite benchmark for the operations workbench.

    python scripts/benchmark_admin_queries.py --schools 2000 --repeat 20

Creates a disposable synthetic database, measures admin repository queries and
prints SQLite query plans. Results are local measurements, not production SLAs.
"""

from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from pathlib import Path
from collections.abc import Callable

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from db.database import Base
from db.models import AdmissionScore, EnrollmentPlan, Major, School
from server.admin import repository
from server.admin.quality import collect_issues

LEVELS = ["985", "211", "双一流", "普通"]
PROVINCES = ["示例省·甲", "示例省·乙", "示例省·丙", "示例省·丁"]
MAJOR_NAMES = [f"基准专业-{i:02d}（合成）" for i in range(20)]


def build_dataset(session, schools_count: int, scores_per_school: int) -> None:
    majors = [
        Major(
            name=name,
            category="工学",
            sub_category="基准类",
            description="benchmark synthetic",
            education_level="本科",
        )
        for name in MAJOR_NAMES
    ]
    session.add_all(majors)
    session.flush()

    schools = [
        School(
            name=f"基准示例院校-{i:04d}（合成）",
            province=PROVINCES[i % len(PROVINCES)],
            city=f"示例市-{i % 7}",
            level=LEVELS[i % len(LEVELS)],
            school_type="综合" if i % 2 == 0 else "理工",
            ranking=100 + i,
            special_type="SYNTHETIC_DEMO_DATA",
            description="benchmark synthetic",
        )
        for i in range(schools_count)
    ]
    session.add_all(schools)
    session.flush()

    scores = []
    plans = []
    for index, school in enumerate(schools):
        for offset in range(scores_per_school):
            major = majors[(index + offset) % len(majors)]
            year = 2020 + (offset % 5)
            scores.append(
                AdmissionScore(
                    school_id=school.id,
                    major_id=major.id,
                    province=school.province,
                    year=year,
                    batch="本科批",
                    subject_type="物理类" if offset % 2 == 0 else "历史类",
                    min_score=500 + (index % 200),
                    avg_score=520 + (index % 180),
                    max_score=550 + (index % 150),
                    min_rank=1000 + index * 3 + offset,
                    plan_count=20,
                )
            )
        plans.append(
            EnrollmentPlan(
                school_id=school.id,
                major_id=majors[index % len(majors)].id,
                province=school.province,
                year=2024,
                plan_count=30,
                subject_requirement="物理必选",
                batch="本科批",
                duration=4,
                tuition=6000,
            )
        )
    session.add_all(scores)
    session.add_all(plans)
    session.commit()


def measure(fn: Callable, repeat: int) -> dict[str, float]:
    fn()  # warm-up
    samples = []
    for _ in range(repeat):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000)
    samples.sort()
    return {
        "median_ms": round(statistics.median(samples), 3),
        "p95_ms": round(samples[min(len(samples) - 1, int(len(samples) * 0.95))], 3),
        "min_ms": round(samples[0], 3),
        "max_ms": round(samples[-1], 3),
    }


def plan(engine, sql: str, params: dict | None = None) -> list[str]:
    with engine.connect() as conn:
        rows = conn.execute(text(f"EXPLAIN QUERY PLAN {sql}"), params or {}).all()
    return [str(row[-1]) for row in rows]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark admin SQLite queries")
    parser.add_argument("--schools", type=int, default=2000)
    parser.add_argument("--scores-per-school", type=int, default=5)
    parser.add_argument("--repeat", type=int, default=20)
    parser.add_argument("--json-out", default="")
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "benchmark.db"
        engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        with engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA busy_timeout=5000"))
            conn.execute(text("PRAGMA synchronous=NORMAL"))
        Base.metadata.create_all(engine)
        factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = factory()
        try:
            build_dataset(session, args.schools, args.scores_per_school)
            total_schools = session.query(School).count()
            total_scores = session.query(AdmissionScore).count()
            total_plans = session.query(EnrollmentPlan).count()
            results: dict[str, object] = {
                "dataset": {
                    "schools": total_schools,
                    "admission_scores": total_scores,
                    "enrollment_plans": total_plans,
                },
                "queries": {
                    "schools_page_1": measure(
                        lambda: repository.list_schools(
                            session,
                            filters={},
                            sort="id",
                            order="asc",
                            page=1,
                            page_size=20,
                        ),
                        args.repeat,
                    ),
                    "schools_deep_page_offset_1980": measure(
                        lambda: repository.list_schools(
                            session,
                            filters={},
                            sort="id",
                            order="asc",
                            page=100,
                            page_size=20,
                        ),
                        args.repeat,
                    ),
                    "schools_filter_province": measure(
                        lambda: repository.list_schools(
                            session,
                            filters={"province": PROVINCES[0]},
                            sort="name",
                            order="asc",
                            page=1,
                            page_size=20,
                        ),
                        args.repeat,
                    ),
                    "school_detail": measure(
                        lambda: repository.get_school_detail(session, 1),
                        args.repeat,
                    ),
                    "stats": measure(lambda: repository.get_stats(session), args.repeat),
                    "quality_scan_province": measure(
                        lambda: collect_issues(session, {"province": PROVINCES[0]}),
                        max(3, args.repeat // 4),
                    ),
                },
                "query_plans": {
                    "admission_lookup": plan(
                        engine,
                        "SELECT * FROM admission_scores "
                        "WHERE school_id = :school_id AND province = :province "
                        "AND year = :year AND subject_type = :subject_type",
                        {"school_id": 1, "province": PROVINCES[0], "year": 2024, "subject_type": "物理类"},
                    ),
                    "schools_by_province": plan(
                        engine,
                        "SELECT * FROM schools WHERE province = :province",
                        {"province": PROVINCES[0]},
                    ),
                    "jobs_by_status": plan(
                        engine,
                        "SELECT * FROM data_quality_jobs WHERE status = :status ORDER BY created_at DESC",
                        {"status": "PENDING"},
                    ),
                },
            }
        finally:
            session.close()
            engine.dispose()

    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
