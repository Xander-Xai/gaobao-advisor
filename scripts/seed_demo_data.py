"""Deterministic SYNTHETIC demo dataset generator.

Every record produced by this module is fabricated. The schools, majors,
provinces, cities, scores and ranks below are invented placeholders. They do
not correspond to any real institution, programme or admissions outcome, and
must never be used to inform a real education decision.

Design constraints:

* **Reproducible** — driven by a fixed seed, so two runs produce byte-identical
  data and CI can assert on it.
* **Self-labelling** — every table carries a provenance marker so a consumer
  reading the database (not just the README) can tell it is synthetic.
* **Unmistakably fake** — institution names use an explicit fictional
  marker and provinces are invented, so the data cannot be mistaken for a real
  admissions table even if detached from this repository.

Run with::

    python -m scripts.seed_demo_data --db data/demo.db --reset
"""

from __future__ import annotations

import argparse

import json
import os
import random
import sys
from datetime import datetime
from pathlib import Path

from config.constants import DEMO_PROVINCES

SYNTHETIC_MARKER = "SYNTHETIC_DEMO_DATA"
SYNTHETIC_NOTICE = (
    "合成演示数据 / SYNTHETIC DEMO DATA — 全部内容为虚构占位，"
    "不对应任何真实院校、专业或录取结果，不得用于真实志愿决策。"
)
# Keep in sync with legacy.gaokao_data.DATA_YEAR: the query layer defaults to
# "current year - 1", so a pinned literal would silently return empty results
# once the calendar advances. Recomputing at seed time keeps a freshly seeded
# demo answerable. Within a given year the output remains fully deterministic.
DEMO_YEAR = datetime.now().year - 1
RANDOM_SEED = 20240617

# Fictional provinces (single source: config.constants). Deliberately not real
# administrative divisions.
DEMO_CITIES = {
    "示例省·甲": ["示例市·晨", "示例市·暮"],
    "示例省·乙": ["示例市·星", "示例市·岚"],
    "示例省·丙": ["示例市·澜"],
    "示例省·丁": ["示例市·砚"],
}

DEMO_SCHOOLS = [
    ("北辰示例科技大学（合成）", "示例省·甲", "示例市·晨", "985", "综合", 1, 1, 1),
    ("海岳示例师范大学（合成）", "示例省·甲", "示例市·晨", "211", "师范", 1, 1, 1),
    ("云栖示例理工大学（合成）", "示例省·乙", "示例市·星", "双一流", "理工", 1, 1, 1),
    ("南岭示例医科大学（合成）", "示例省·乙", "示例市·星", "普通", "医药", 0, 0, 0),
    ("东洲示例财经大学（合成）", "示例省·丙", "示例市·澜", "211", "财经", 0, 1, 1),
    ("西岭示例工业大学（合成）", "示例省·丙", "示例市·澜", "普通", "理工", 0, 0, 0),
    ("沧澜示例农业大学（合成）", "示例省·丁", "示例市·砚", "普通", "综合", 0, 0, 0),
    ("长风示例师范大学（合成）", "示例省·丁", "示例市·砚", "普通", "师范", 0, 0, 0),
]

DEMO_MAJORS = [
    ("计算机科学与技术（合成）", "工学", "计算机类", 0.93, 18500, 16500),
    ("软件工程（合成）", "工学", "计算机类", 0.94, 19200, 17100),
    ("电子信息工程（合成）", "工学", "电子信息类", 0.92, 15800, 14100),
    ("临床医学（合成）", "医学", "临床医学类", 0.97, 12400, 11600),
    ("药学（合成）", "医学", "药学类", 0.90, 11300, 10400),
    ("数学与应用数学（合成）", "理学", "数学类", 0.86, 14200, 12900),
    ("应用统计学（合成）", "理学", "统计学类", 0.88, 15600, 13900),
    ("汉语言文学（合成）", "文学", "中国语言文学类", 0.84, 11900, 10800),
    ("会计学（合成）", "经济学", "会计学", 0.91, 13800, 12600),
    ("金融学（合成）", "经济学", "金融学类", 0.90, 16200, 14400),
    ("机械设计制造及其自动化（合成）", "工学", "机械类", 0.85, 12900, 11700),
    ("土木工程（合成）", "工学", "土木类", 0.82, 12100, 11100),
]

DEMO_SUBJECT_TYPES = ["物理类", "历史类"]


def _seeded_random() -> random.Random:
    return random.Random(RANDOM_SEED)


def build_payload() -> dict:
    """Return the full synthetic dataset as plain dicts.

    Pure function of :data:`RANDOM_SEED` — no I/O, no database access.
    """
    rng = _seeded_random()

    schools = [
        {
            "name": name,
            "province": province,
            "city": city,
            "level": level,
            "school_type": school_type,
            "is_985": is_985,
            "is_211": is_211,
            "is_double_first_class": is_dfc,
            "ranking": 10 + idx * 7,
            "website": None,
            "description": SYNTHETIC_NOTICE,
            "special_type": SYNTHETIC_MARKER,
            "data_source_note": "合成演示数据，无真实来源",
        }
        for idx, (name, province, city, level, school_type, is_985, is_211, is_dfc) in enumerate(DEMO_SCHOOLS)
    ]

    majors = [
        {
            "name": name,
            "category": category,
            "sub_category": sub_category,
            "employment_rate": employment_rate,
            "avg_salary": avg_salary,
            "median_salary": median,
            "salary_range": json.dumps({"low": int(median * 0.8), "high": int(median * 1.35)}, ensure_ascii=False),
            "top_industries": json.dumps(["示例行业·甲", "示例行业·乙", "示例行业·丙"], ensure_ascii=False),
            "employment_locations": json.dumps([DEMO_CITIES[prov][0] for prov in DEMO_CITIES], ensure_ascii=False),
            "postgraduate_rate": round(rng.uniform(0.15, 0.45), 3),
            "overseas_rate": round(rng.uniform(0.02, 0.12), 3),
            "description": SYNTHETIC_NOTICE,
            "job_directions": json.dumps(["示例岗位·甲", "示例岗位·乙"], ensure_ascii=False),
            "is_hot": 1 if rng.random() > 0.6 else 0,
            "education_level": "本科",
        }
        for (name, category, sub_category, employment_rate, avg_salary, median) in DEMO_MAJORS
    ]

    admission_scores = []
    for school_idx, school in enumerate(schools):
        for major_idx, major in enumerate(majors):
            if (school_idx + major_idx) % 3 != 0:
                continue
            for province in DEMO_PROVINCES:
                subject_type = DEMO_SUBJECT_TYPES[(school_idx + major_idx) % 2]
                base = 520 + school_idx * 6 - major_idx * 2 + rng.randint(-8, 8)
                min_score = max(300, min(750, base))
                max_score = min(750, min_score + rng.randint(18, 45))
                admission_scores.append(
                    {
                        "school_idx": school_idx,
                        "major_idx": major_idx,
                        "province": province,
                        "year": DEMO_YEAR,
                        "batch": "本科批",
                        "standardized_batch": "本科批",
                        "subject_type": subject_type,
                        "min_score": min_score,
                        "avg_score": round((min_score + max_score) / 2, 1),
                        "max_score": max_score,
                        "min_rank": rng.randint(1_200, 88_000),
                        "plan_count": rng.randint(20, 180),
                    }
                )

    enrollment_plans = []
    for school_idx, school in enumerate(schools):
        for major_idx, major in enumerate(majors):
            if (school_idx * 2 + major_idx) % 4 != 0:
                continue
            for province in DEMO_PROVINCES[:2]:
                enrollment_plans.append(
                    {
                        "school_idx": school_idx,
                        "major_idx": major_idx,
                        "province": province,
                        "year": DEMO_YEAR,
                        "plan_count": rng.randint(15, 120),
                        "subject_requirement": "物理必选" if major_idx % 2 == 0 else "不限",
                        "batch": "本科批",
                        "duration": 4,
                        "tuition": rng.choice([5000, 6000, 7000, 8000]),
                    }
                )

    subject_rankings = []
    for school_idx, school in enumerate(schools):
        for category in sorted({m["category"] for m in majors}):
            subject_rankings.append(
                {
                    "school_idx": school_idx,
                    "major_category": category,
                    "ranking_source": "示例排名（合成）",
                    "ranking_year": DEMO_YEAR,
                    "ranking_position": rng.randint(5, 60),
                    "grade": rng.choice(["A", "A-", "B+", "B", "B-"]),
                }
            )

    return {
        "metadata": {
            "marker": SYNTHETIC_MARKER,
            "notice": SYNTHETIC_NOTICE,
            "seed": RANDOM_SEED,
            "year": DEMO_YEAR,
            "dataset_version": "1.0.0",
            "disclaimer": "本数据集为程序生成的虚构数据，不可用于真实志愿决策。",
        },
        "schools": schools,
        "majors": majors,
        "admission_scores": admission_scores,
        "enrollment_plans": enrollment_plans,
        "subject_rankings": subject_rankings,
    }


def _bind_engine(db_path: Path):
    """Return an engine bound to ``db_path``, reusing modules if already loaded.

    ``db.database`` builds its engine from ``DATABASE_URL`` at import time. If
    it has already been imported (which it will be once any test has touched
    the app), re-importing the package would create a *second* set of ORM
    classes and break every caller holding the first. Instead, rebind the
    existing module in place.
    """
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.resolve()}"

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import db.database as database

    if getattr(database, "DATABASE_URL", None) == os.environ["DATABASE_URL"]:
        return database.engine, database.SessionLocal

    engine = create_engine(
        os.environ["DATABASE_URL"],
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
        future=True,
    )
    database.engine = engine
    database.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, database.SessionLocal


def seed_database(db_path: str | Path, reset: bool = False) -> dict[str, int]:
    """Create schema and load the synthetic dataset. Returns row counts.

    Args:
        db_path: target SQLite file.
        reset: delete an existing file first.

    Returns:
        Mapping of table name to inserted row count.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if reset and db_path.exists():
        db_path.unlink()

    _engine, SessionLocal = _bind_engine(db_path)

    from db.database import init_db
    from db.models import AdmissionScore, EnrollmentPlan, Major, School, SubjectRanking

    init_db()

    payload = build_payload()
    session = SessionLocal()
    try:
        schools = [School(**row) for row in payload["schools"]]
        session.add_all(schools)
        session.flush()

        majors = [Major(**row) for row in payload["majors"]]
        session.add_all(majors)
        session.flush()

        session.add_all(
            [
                AdmissionScore(
                    school_id=schools[row["school_idx"]].id,
                    major_id=majors[row["major_idx"]].id,
                    province=row["province"],
                    year=row["year"],
                    batch=row["batch"],
                    standardized_batch=row["standardized_batch"],
                    subject_type=row["subject_type"],
                    min_score=row["min_score"],
                    avg_score=row["avg_score"],
                    max_score=row["max_score"],
                    min_rank=row["min_rank"],
                    plan_count=row["plan_count"],
                )
                for row in payload["admission_scores"]
            ]
        )
        session.add_all(
            [
                EnrollmentPlan(
                    school_id=schools[row["school_idx"]].id,
                    major_id=majors[row["major_idx"]].id,
                    province=row["province"],
                    year=row["year"],
                    plan_count=row["plan_count"],
                    subject_requirement=row["subject_requirement"],
                    batch=row["batch"],
                    duration=row["duration"],
                    tuition=row["tuition"],
                )
                for row in payload["enrollment_plans"]
            ]
        )
        session.add_all(
            [
                SubjectRanking(
                    school_id=schools[row["school_idx"]].id,
                    major_category=row["major_category"],
                    ranking_source=row["ranking_source"],
                    ranking_year=row["ranking_year"],
                    ranking_position=row["ranking_position"],
                    grade=row["grade"],
                )
                for row in payload["subject_rankings"]
            ]
        )
        session.commit()

        counts = {
            "schools": len(payload["schools"]),
            "majors": len(payload["majors"]),
            "admission_scores": len(payload["admission_scores"]),
            "enrollment_plans": len(payload["enrollment_plans"]),
            "subject_rankings": len(payload["subject_rankings"]),
        }
    finally:
        session.close()

    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the SYNTHETIC demo database")
    parser.add_argument("--db", default="data/demo.db", help="target SQLite path")
    parser.add_argument("--reset", action="store_true", help="delete existing db first")
    parser.add_argument("--json-out", default="", help="also write payload metadata as JSON")
    args = parser.parse_args(argv)

    payload = build_payload()

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote payload: {out}")

    counts = seed_database(args.db, reset=args.reset)
    print(f"{SYNTHETIC_MARKER}: {SYNTHETIC_NOTICE}")
    for table, count in counts.items():
        print(f"  {table:<20} {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
