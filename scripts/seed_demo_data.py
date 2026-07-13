#!/usr/bin/env python3
"""Create an idempotent SQLite database containing synthetic demo records."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = PROJECT_ROOT / "data" / "sample" / "demo_admissions.json"
SYNTHETIC_MARKER = "SYNTHETIC DEMO DATA - NOT FOR REAL ADMISSION DECISIONS"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=PROJECT_ROOT / "data" / "demo.db",
        help="SQLite database to create or update",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    database_path = args.database.expanduser().resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)

    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    if dataset.get("metadata", {}).get("synthetic") is not True:
        raise RuntimeError("demo dataset is missing the required synthetic marker")

    os.environ["GAOBAO__DB_PATH"] = str(database_path)
    os.environ.pop("DATABASE_URL", None)
    sys.path.insert(0, str(PROJECT_ROOT))

    from db.database import get_session, init_db
    from db.models import AdmissionScore, Major, School

    init_db()
    session = get_session()
    try:
        schools: dict[str, School] = {}
        for record in dataset["schools"]:
            school = session.query(School).filter(School.name == record["name"]).one_or_none()
            if school is None:
                school = School(name=record["name"])
                session.add(school)
            school.province = record["province"]
            school.city = record["city"]
            school.level = record["level"]
            school.school_type = record["school_type"]
            school.data_source_note = SYNTHETIC_MARKER
            schools[school.name] = school

        majors: dict[str, Major] = {}
        for record in dataset["majors"]:
            major = session.query(Major).filter(Major.name == record["name"]).one_or_none()
            if major is None:
                major = Major(name=record["name"])
                session.add(major)
            major.category = record["category"]
            major.sub_category = record["sub_category"]
            major.description = SYNTHETIC_MARKER
            majors[major.name] = major

        session.flush()

        for record in dataset["admission_scores"]:
            school = schools[record["school"]]
            major = majors[record["major"]]
            score = (
                session.query(AdmissionScore)
                .filter(
                    AdmissionScore.school_id == school.id,
                    AdmissionScore.major_id == major.id,
                    AdmissionScore.province == record["province"],
                    AdmissionScore.year == record["year"],
                    AdmissionScore.batch == record["batch"],
                    AdmissionScore.subject_type == record["subject_type"],
                )
                .one_or_none()
            )
            if score is None:
                score = AdmissionScore(
                    school_id=school.id,
                    major_id=major.id,
                    province=record["province"],
                    year=record["year"],
                    batch=record["batch"],
                    subject_type=record["subject_type"],
                )
                session.add(score)
            score.min_score = record["min_score"]
            score.min_rank = record["min_rank"]

        session.commit()
    finally:
        session.close()

    print(f"synthetic demo database ready: {database_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
