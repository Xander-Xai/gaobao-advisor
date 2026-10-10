#!/usr/bin/env python3
"""Measure the real state of a gaokao database and refuse to pass an empty one.

The report is intentionally conservative: a database with no admission data is
reported as ``blocked`` rather than as "0% missing, 0 duplicates, therefore
fine". Every metric is measured against the database that was actually opened,
never against numbers carried over from a previous run.

Examples
--------
    python scripts/data_quality_report.py --database data/gaokao.db
    python scripts/data_quality_report.py --database data/gaokao.db --json report.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import OrderedDict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.db_archive import detect_format  # noqa: E402

BUSINESS_KEY = ("school_id", "major_id", "province", "year", "batch", "subject_type")
PAYLOAD_COLUMNS = ("min_score", "avg_score", "max_score", "min_rank", "plan_count", "standardized_batch")

VERDICT_OK = "ok"
VERDICT_DEGRADED = "degraded"
VERDICT_BLOCKED = "blocked"

MIN_ROWS_FOR_COVERAGE = 1
FRESH_YEAR = date.today().year - 1
FRESH_WINDOW = 2

REQUIRED_TABLES = ("schools", "majors", "admission_scores")

NON_PROVINCE_LABELS = frozenset({"ALL", "全国", "不分", "-", "N/A", "NA"})


class EmptyDatabase(RuntimeError):
    """Raised when the database cannot support any coverage statement."""


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _table_names(connection: sqlite3.Connection) -> list[str]:
    return [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]


def _scalar(connection: sqlite3.Connection, sql: str) -> int:
    return connection.execute(sql).fetchone()[0]


def _columns(connection: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')]


def analyse(database: Path) -> OrderedDict:
    """Return every measured metric for the database at ``database``."""
    database = Path(database)
    findings: list[dict] = []
    checks: list[dict] = []

    if not database.exists():
        raise EmptyDatabase(f"database not found: {database}")

    detected = detect_format(database)
    if detected.name != "sqlite":
        raise EmptyDatabase(f"{database} is a {detected.name!r} file, not a SQLite database")

    connection = _connect(database)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        tables = _table_names(connection)
        missing_tables = [name for name in REQUIRED_TABLES if name not in tables]
        if missing_tables:
            raise EmptyDatabase(f"missing required tables: {', '.join(missing_tables)}")

        counts = {name: _scalar(connection, f'SELECT COUNT(*) FROM "{name}"') for name in tables}

        if counts["admission_scores"] < MIN_ROWS_FOR_COVERAGE:
            raise EmptyDatabase(
                f"admission_scores holds {counts['admission_scores']} rows; "
                "coverage, freshness and duplicate metrics are undefined on an empty dataset"
            )

        score_columns = _columns(connection, "admission_scores")
        payload = [name for name in PAYLOAD_COLUMNS if name in score_columns]
        business_key = [name for name in BUSINESS_KEY if name in score_columns]

        quoted_key = ",".join(f'"{name}"' for name in business_key)
        quoted_payload = ",".join(f'ifnull("{name}", "")' for name in payload)
        full_row = ",".join(f'"{name}"' for name in score_columns if name != "id")

        total_scores = counts["admission_scores"]
        exact_duplicate_rows = _scalar(
            connection,
            f"SELECT COALESCE(SUM(c - 1), 0) FROM "
            f"(SELECT COUNT(*) c FROM admission_scores GROUP BY {full_row} HAVING COUNT(*) > 1)",
        )
        exact_duplicate_groups = _scalar(
            connection,
            f"SELECT COUNT(*) FROM (SELECT 1 FROM admission_scores GROUP BY {full_row} HAVING COUNT(*) > 1)",
        )
        if business_key:
            key_duplicate_rows = _scalar(
                connection,
                f"SELECT COALESCE(SUM(c - 1), 0) FROM "
                f"(SELECT COUNT(*) c FROM admission_scores GROUP BY {quoted_key} HAVING COUNT(*) > 1)",
            )
            key_duplicate_groups = _scalar(
                connection,
                f"SELECT COUNT(*) FROM (SELECT 1 FROM admission_scores GROUP BY {quoted_key} HAVING COUNT(*) > 1)",
            )
            conflicting_key_groups = (
                _scalar(
                    connection,
                    f"SELECT COUNT(*) FROM (SELECT 1 FROM admission_scores GROUP BY {quoted_key} "
                    f"HAVING COUNT(DISTINCT printf('%s', {quoted_payload})) > 1)",
                )
                if payload
                else 0
            )
        else:
            key_duplicate_rows = key_duplicate_groups = conflicting_key_groups = 0

        years = {
            row[0]: row[1] for row in connection.execute("SELECT year, COUNT(*) FROM admission_scores GROUP BY year")
        }
        latest_year = max(years) if years else None
        stale_years = latest_year is not None and (date.today().year - latest_year) > FRESH_WINDOW

        total_schools = counts.get("schools", 0)
        schools_with_scores = _scalar(connection, "SELECT COUNT(DISTINCT school_id) FROM admission_scores")
        schools_without_scores = (
            _scalar(
                connection,
                "SELECT COUNT(*) FROM schools s WHERE NOT EXISTS "
                "(SELECT 1 FROM admission_scores a WHERE a.school_id = s.id)",
            )
            if total_schools
            else 0
        )
        coverage = (schools_with_scores / total_schools * 100) if total_schools else 0.0

        provinces = {
            row[0]: row[1]
            for row in connection.execute(
                "SELECT province, COUNT(*) FROM admission_scores GROUP BY province ORDER BY COUNT(*) DESC"
            )
        }
        non_province_rows = sum(
            count
            for province, count in provinces.items()
            if not province or province.strip().upper() in NON_PROVINCE_LABELS
        )
        real_provinces = len([p for p in provinces if p and p.strip().upper() not in NON_PROVINCE_LABELS])

        majors_total = counts.get("majors", 0)
        majors_with_scores = _scalar(
            connection, "SELECT COUNT(DISTINCT major_id) FROM admission_scores WHERE major_id IS NOT NULL"
        )
        major_coverage = (majors_with_scores / majors_total * 100) if majors_total else 0.0

        rows_missing_min_score = _scalar(connection, "SELECT COUNT(*) FROM admission_scores WHERE min_score IS NULL")
        rows_missing_min_rank = _scalar(connection, "SELECT COUNT(*) FROM admission_scores WHERE min_rank IS NULL")
        rows_null_major = _scalar(connection, "SELECT COUNT(*) FROM admission_scores WHERE major_id IS NULL")
        schools_missing_province = _scalar(
            connection, "SELECT COUNT(*) FROM schools WHERE province IS NULL OR TRIM(province) = ''"
        )

        out_of_range_scores = _scalar(
            connection,
            "SELECT COUNT(*) FROM admission_scores WHERE min_score < 60 OR (min_score > 750 AND province != '海南')",
        )
    finally:
        connection.close()

    def add(check: str, status: str, detail: str) -> None:
        checks.append({"check": check, "status": status, "detail": detail})
        if status == VERDICT_BLOCKED:
            findings.append(detail)
        elif status == VERDICT_DEGRADED:
            findings.append(detail)

    add("integrity", VERDICT_OK if integrity == "ok" else VERDICT_BLOCKED, f"PRAGMA integrity_check = {integrity}")
    add(
        "school_coverage",
        VERDICT_OK if coverage >= 90 else VERDICT_DEGRADED,
        f"{schools_with_scores}/{total_schools} schools have admission data ({coverage:.1f}%)",
    )
    add(
        "major_coverage",
        VERDICT_OK if major_coverage >= 80 else VERDICT_DEGRADED,
        f"{majors_with_scores}/{majors_total} majors appear in admission data ({major_coverage:.1f}%)",
    )
    add(
        "freshness",
        VERDICT_OK if not stale_years else VERDICT_BLOCKED,
        f"latest admission year is {latest_year} (current year {date.today().year}, window {FRESH_WINDOW})",
    )
    add(
        "exact_duplicates",
        VERDICT_OK if exact_duplicate_rows == 0 else VERDICT_DEGRADED,
        f"{exact_duplicate_rows} byte-identical rows in {exact_duplicate_groups} groups are safe to deduplicate",
    )
    add(
        "business_key_duplicates",
        VERDICT_OK if key_duplicate_rows == 0 else VERDICT_DEGRADED,
        f"{key_duplicate_rows} rows share a business key across {key_duplicate_groups} groups; "
        f"{conflicting_key_groups} of those groups disagree on payload and must not be deduplicated blindly",
    )
    add(
        "null_scores",
        VERDICT_OK if rows_missing_min_score == 0 else VERDICT_DEGRADED,
        f"{rows_missing_min_score} admission rows have no min_score",
    )
    add(
        "null_ranks",
        VERDICT_OK if rows_missing_min_rank / total_scores < 0.5 else VERDICT_DEGRADED,
        f"{rows_missing_min_rank} admission rows have no min_rank ({rows_missing_min_rank / total_scores * 100:.1f}%)",
    )
    add(
        "rows_without_major",
        VERDICT_OK if rows_null_major == 0 else VERDICT_DEGRADED,
        f"{rows_null_major} admission rows are not linked to a major (school-level only)",
    )
    add(
        "schools_without_province",
        VERDICT_OK if schools_missing_province == 0 else VERDICT_DEGRADED,
        f"{schools_missing_province} schools have no province",
    )
    add(
        "score_range",
        VERDICT_OK if out_of_range_scores == 0 else VERDICT_DEGRADED,
        f"{out_of_range_scores} rows have a min_score outside 60..750 (海南 exempt)",
    )
    add(
        "province_coverage",
        VERDICT_OK if real_provinces >= 31 else VERDICT_DEGRADED,
        f"{real_provinces} real provinces carry admission data "
        f"({len(provinces) - real_provinces} bucket(s) hold placeholder labels)",
    )
    add(
        "province_labels",
        VERDICT_OK if non_province_rows == 0 else VERDICT_DEGRADED,
        f"{non_province_rows} admission rows carry a placeholder province label such as 'ALL'",
    )

    blocked = any(check["status"] == VERDICT_BLOCKED for check in checks)
    verdict = VERDICT_BLOCKED if blocked else (VERDICT_DEGRADED if findings else VERDICT_OK)

    return OrderedDict(
        [
            ("database", str(database)),
            ("verdict", verdict),
            ("row_counts", counts),
            ("totals", {"admission_scores": total_scores, "schools": total_schools, "majors": majors_total}),
            ("years", dict(sorted(years.items()))),
            ("latest_year", latest_year),
            ("provinces", provinces),
            ("real_province_count", real_provinces),
            ("school_coverage_pct", round(coverage, 2)),
            ("major_coverage_pct", round(major_coverage, 2)),
            (
                "duplicates",
                {
                    "exact_rows": exact_duplicate_rows,
                    "exact_groups": exact_duplicate_groups,
                    "business_key_rows": key_duplicate_rows,
                    "business_key_groups": key_duplicate_groups,
                    "conflicting_payload_groups": conflicting_key_groups,
                },
            ),
            (
                "completeness",
                {
                    "rows_missing_min_score": rows_missing_min_score,
                    "rows_missing_min_rank": rows_missing_min_rank,
                    "rows_without_major": rows_null_major,
                    "schools_without_scores": schools_without_scores,
                    "schools_missing_province": schools_missing_province,
                    "out_of_range_scores": out_of_range_scores,
                },
            ),
            ("checks", checks),
            ("findings", findings),
        ]
    )


def render(report: OrderedDict) -> str:
    lines: list[str] = []
    add = lines.append
    add("=" * 72)
    add(f"  DATA QUALITY REPORT — verdict: {report['verdict'].upper()}")
    add("=" * 72)
    add(f"\ndatabase: {report['database']}")

    add("\n-- row counts " + "-" * 56)
    for name, count in report["row_counts"].items():
        add(f"   {name:<26} {count:>12,}")

    add("\n-- coverage " + "-" * 60)
    add(f"   schools with admission data : {report['school_coverage_pct']}%")
    add(f"   majors with admission data  : {report['major_coverage_pct']}%")
    add(f"   provinces with data         : {len(report['provinces'])}")

    add("\n-- freshness " + "-" * 59)
    for year, count in report["years"].items():
        add(f"   {year}: {count:>12,}")
    add(f"   latest year: {report['latest_year']}")

    add("\n-- duplicates " + "-" * 58)
    dup = report["duplicates"]
    add(f"   byte-identical rows   : {dup['exact_rows']:>8,} in {dup['exact_groups']:,} groups (safe to dedupe)")
    add(f"   business-key rows     : {dup['business_key_rows']:>8,} in {dup['business_key_groups']:,} groups")
    add(f"   conflicting payloads  : {dup['conflicting_payload_groups']:>8,} groups (do NOT dedupe blindly)")

    add("\n-- completeness " + "-" * 55)
    for name, value in report["completeness"].items():
        add(f"   {name:<28} {value:>12,}")

    add("\n-- provinces " + "-" * 57)
    for province, count in list(report["provinces"].items()):
        add(f"   {province or '(empty)':<10} {count:>12,}")

    add("\n-- checks " + "-" * 62)
    for check in report["checks"]:
        marker = {"ok": "PASS", "degraded": "WARN", "blocked": "BLOCK"}.get(check["status"], check["status"])
        add(f"   [{marker:>5}] {check['check']:<26} {check['detail']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database", type=Path, default=Path("data/gaokao.db"))
    parser.add_argument("--json", type=Path, default=None, help="Also write the machine-readable report here")
    parser.add_argument(
        "--fail-on",
        choices=(VERDICT_OK, VERDICT_DEGRADED, VERDICT_BLOCKED),
        default=VERDICT_BLOCKED,
        help="Exit non-zero at or above this severity (default: blocked)",
    )
    args = parser.parse_args(argv)

    try:
        report = analyse(args.database)
    except EmptyDatabase as exc:
        print(f"BLOCKED data quality cannot be established: {exc}", file=sys.stderr)
        print(
            "An empty or unusable database must never be reported as '0% missing, 0 duplicates, therefore healthy'.",
            file=sys.stderr,
        )
        return 2

    print(render(report))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\njson report written to {args.json}")

    severity = {VERDICT_OK: 0, VERDICT_DEGRADED: 1, VERDICT_BLOCKED: 2}[report["verdict"]]
    threshold = {VERDICT_OK: 0, VERDICT_DEGRADED: 1, VERDICT_BLOCKED: 2}[args.fail_on]
    if severity >= threshold and report["verdict"] != VERDICT_OK:
        return 1 if args.fail_on != VERDICT_OK else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
