"""Tests for the data quality report and the tiered deduplication planner."""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from scripts.data_quality_report import VERDICT_BLOCKED, VERDICT_DEGRADED, EmptyDatabase, analyse
from scripts.data_quality_report import main as quality_main
from scripts.dedupe_admission_scores import build_plan, exact_delete_sql
from scripts.dedupe_admission_scores import main as dedupe_main

SCHEMA = """
CREATE TABLE schools (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    province TEXT
);
CREATE TABLE majors (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE admission_scores (
    id INTEGER PRIMARY KEY,
    school_id INTEGER NOT NULL,
    major_id INTEGER,
    province TEXT NOT NULL,
    year INTEGER NOT NULL,
    batch TEXT NOT NULL,
    subject_type TEXT NOT NULL,
    min_score INTEGER,
    avg_score FLOAT,
    max_score INTEGER,
    min_rank INTEGER,
    plan_count INTEGER,
    standardized_batch TEXT
);
"""


def _schema_only(path: Path) -> Path:
    connection = sqlite3.connect(path)
    connection.executescript(SCHEMA)
    connection.commit()
    connection.close()
    return path


def _populated(path: Path, *, year: int | None = None, duplicates: bool = False) -> Path:
    year = year or date.today().year
    connection = sqlite3.connect(path)
    connection.executescript(SCHEMA)
    connection.executemany(
        "INSERT INTO schools (id, name, province) VALUES (?, ?, ?)",
        [(1, "甲大学", "河北"), (2, "乙大学", "河北"), (3, "丙大学", "山西")],
    )
    connection.executemany("INSERT INTO majors (id, name) VALUES (?, ?)", [(1, "计算机"), (2, "临床医学")])
    rows = [
        (1, 1, 1, "河北", year, "本科批", "物理", 600, 610.0, 620, 1000, 10, "本科批"),
        (2, 2, 2, "河北", year, "本科批", "物理", 580, 585.0, 590, 2000, 8, "本科批"),
        (3, 2, 2, "山西", year, "本科批", "历史", 570, 575.0, 580, 1500, 5, "本科批"),
        (4, 3, 2, "山西", year, "本科批", "物理", 560, 565.0, 570, 3000, 4, "本科批"),
    ]
    connection.executemany(
        "INSERT INTO admission_scores "
        "(id, school_id, major_id, province, year, batch, subject_type, min_score, avg_score, max_score, min_rank, plan_count, standardized_batch) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    if duplicates:
        connection.executemany(
            "INSERT INTO admission_scores "
            "(id, school_id, major_id, province, year, batch, subject_type, min_score, avg_score, max_score, min_rank, plan_count, standardized_batch) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (99, 1, 1, "河北", year, "本科批", "物理", 600, 610.0, 620, 1000, 10, "本科批"),
                (98, 2, 2, "河北", year, "本科批", "物理", 579, 584.0, 589, 2100, 7, "本科批"),
            ],
        )
    connection.commit()
    connection.close()
    return path


def test_empty_file_is_blocked_not_reported_healthy(tmp_path: Path) -> None:
    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).close()

    with pytest.raises(EmptyDatabase):
        analyse(empty)


def test_schema_without_rows_is_blocked(tmp_path: Path) -> None:
    database = _schema_only(tmp_path / "schema.db")

    with pytest.raises(EmptyDatabase) as excinfo:
        analyse(database)

    assert "admission_scores" in str(excinfo.value)


def test_missing_required_table_is_blocked(tmp_path: Path) -> None:
    database = tmp_path / "partial.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE schools (id INTEGER PRIMARY KEY, name TEXT, province TEXT)")
    connection.commit()
    connection.close()

    with pytest.raises(EmptyDatabase):
        analyse(database)


def test_quality_main_exits_nonzero_for_empty_database(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).close()

    code = quality_main(["--database", str(empty)])

    assert code == 2
    assert "must never be reported" in capsys.readouterr().err


def test_populated_database_reports_measured_metrics(tmp_path: Path) -> None:
    database = _populated(tmp_path / "data.db")

    report = analyse(database)

    assert report["totals"]["admission_scores"] == 4
    assert report["school_coverage_pct"] == 100.0
    assert report["major_coverage_pct"] == 100.0
    assert report["latest_year"] == date.today().year
    assert report["duplicates"]["exact_rows"] == 0
    assert report["real_province_count"] == 2
    assert report["verdict"] == VERDICT_DEGRADED


def test_stale_data_blocks_the_report(tmp_path: Path) -> None:
    database = _populated(tmp_path / "stale.db", year=date.today().year - 5)

    report = analyse(database)

    assert report["verdict"] == VERDICT_BLOCKED
    freshness = next(check for check in report["checks"] if check["check"] == "freshness")
    assert freshness["status"] == VERDICT_BLOCKED


def test_placeholder_province_label_is_flagged(tmp_path: Path) -> None:
    database = _populated(tmp_path / "data.db")
    connection = sqlite3.connect(database)
    connection.execute(
        "INSERT INTO admission_scores "
        "(school_id, major_id, province, year, batch, subject_type, min_score) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (1, 1, "ALL", date.today().year, "本科批", "物理", 500),
    )
    connection.commit()
    connection.close()

    report = analyse(database)

    label_check = next(check for check in report["checks"] if check["check"] == "province_labels")
    assert label_check["status"] == VERDICT_DEGRADED
    assert report["real_province_count"] == 2


def test_json_report_is_written(tmp_path: Path) -> None:
    database = _populated(tmp_path / "data.db")
    destination = tmp_path / "out" / "report.json"

    code = quality_main(["--database", str(database), "--json", str(destination), "--fail-on", "ok"])

    assert code == 0
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["totals"]["admission_scores"] == 4


def test_dedupe_plan_separates_exact_from_conflicting(tmp_path: Path) -> None:
    database = _populated(tmp_path / "data.db", duplicates=True)

    plan = build_plan(database)

    assert plan["exact_tier"]["rows_to_delete"] == 1
    assert plan["exact_tier"]["groups"] == 1
    assert plan["conflicting_tier"]["groups"] == 1
    assert plan["conflicting_tier"]["rows_in_conflict"] == 1


def test_exact_delete_sql_never_groups_by_id(tmp_path: Path) -> None:
    database = _populated(tmp_path / "data.db", duplicates=True)

    sql = exact_delete_sql(database)

    assert '"id"' not in sql
    assert "MIN(id)" in sql
    assert "school_id" in sql


def test_dedupe_dry_run_deletes_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    database = _populated(tmp_path / "data.db", duplicates=True)
    before = analyse(database)["totals"]["admission_scores"]

    code = dedupe_main(["--database", str(database)])

    assert code == 0
    assert "DRY RUN" in capsys.readouterr().out
    assert analyse(database)["totals"]["admission_scores"] == before


def test_dedupe_apply_against_live_path_requires_opt_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    database = _populated(tmp_path / "live.db", duplicates=True)
    monkeypatch.setattr("scripts.dedupe_admission_scores.LIVE_DATABASE", database)

    code = dedupe_main(["--database", str(database), "--apply"])

    assert code == 2
    assert "allow-live-database" in capsys.readouterr().err
    assert analyse(database)["totals"]["admission_scores"] == 6


def test_dedupe_apply_on_live_path_proceeds_with_explicit_opt_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _populated(tmp_path / "live.db", duplicates=True)
    monkeypatch.setattr("scripts.dedupe_admission_scores.LIVE_DATABASE", database)

    code = dedupe_main(
        ["--database", str(database), "--apply", "--allow-live-database", "--delete-log-dir", str(tmp_path / "logs")]
    )

    assert code == 0
    assert analyse(database)["totals"]["admission_scores"] == 5


def test_dedupe_apply_removes_only_tier_one_and_keeps_conflicts(tmp_path: Path) -> None:
    source = _populated(tmp_path / "source.db", duplicates=True)
    copy = tmp_path / "copy.db"
    log_dir = tmp_path / "logs"

    code = dedupe_main(
        ["--database", str(source), "--dry-run-copy", str(copy), "--apply", "--delete-log-dir", str(log_dir)]
    )

    assert code == 0
    report = analyse(copy)
    assert report["totals"]["admission_scores"] == 5
    assert report["duplicates"]["exact_rows"] == 0
    assert report["duplicates"]["conflicting_payload_groups"] == 1
    logs = list(log_dir.glob("dedupe_deleted_ids_*.json"))
    assert len(logs) == 1
    assert json.loads(logs[0].read_text(encoding="utf-8"))["count"] == 1


def test_dedupe_apply_leaves_source_untouched_when_copy_used(tmp_path: Path) -> None:
    source = _populated(tmp_path / "source.db", duplicates=True)
    copy = tmp_path / "copy.db"

    code = dedupe_main(
        ["--database", str(source), "--dry-run-copy", str(copy), "--apply", "--delete-log-dir", str(tmp_path / "logs")]
    )

    assert code == 0
    assert analyse(source)["totals"]["admission_scores"] == 6
    assert analyse(copy)["totals"]["admission_scores"] == 5
