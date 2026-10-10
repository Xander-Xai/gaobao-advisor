"""Tests for the synthetic, idempotent community demo dataset."""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_demo_dataset_is_explicitly_synthetic():
    dataset_path = Path("data/sample/demo_admissions.json")

    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))

    assert dataset["metadata"]["synthetic"] is True
    assert dataset["metadata"]["license"] == "CC0-1.0"
    assert "真实" in dataset["metadata"]["warning"]
    assert dataset["schools"]
    assert all(school["synthetic"] is True for school in dataset["schools"])
    assert all("示例" in school["name"] for school in dataset["schools"])


def test_demo_seed_is_idempotent_and_marks_every_record(tmp_path):
    database_path = tmp_path / "demo.db"
    command = [
        sys.executable,
        "scripts/seed_demo_data.py",
        "--database",
        str(database_path),
    ]

    first = subprocess.run(command, check=True, capture_output=True, text=True)
    second = subprocess.run(command, check=True, capture_output=True, text=True)

    assert "synthetic demo database ready" in first.stdout
    assert "synthetic demo database ready" in second.stdout

    connection = sqlite3.connect(database_path)
    try:
        school_count = connection.execute("SELECT COUNT(*) FROM schools").fetchone()[0]
        major_count = connection.execute("SELECT COUNT(*) FROM majors").fetchone()[0]
        score_count = connection.execute("SELECT COUNT(*) FROM admission_scores").fetchone()[0]
        school_markers = connection.execute(
            "SELECT COUNT(*) FROM schools WHERE data_source_note LIKE 'SYNTHETIC DEMO DATA%'"
        ).fetchone()[0]
        real_school_count = connection.execute(
            "SELECT COUNT(*) FROM schools WHERE name IN ('清华大学', '北京大学', '复旦大学')"
        ).fetchone()[0]
    finally:
        connection.close()

    assert (school_count, major_count, score_count) == (3, 3, 6)
    assert school_markers == school_count
    assert real_school_count == 0
