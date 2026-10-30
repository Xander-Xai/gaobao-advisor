"""Alembic migration smoke test on a disposable SQLite database."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

ROOT = Path(__file__).resolve().parent.parent


def test_alembic_upgrade_creates_admin_tables(tmp_path):
    db = tmp_path / "migrate.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db}", "APP_ENV": "development"}
    result = subprocess.run(
        [sys.executable, "-m", "db.migrate", "upgrade"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 and "No module named 'alembic'" in result.stderr:
        pytest.skip("alembic is not installed (install the mysql/dev extra)")
    assert result.returncode == 0, result.stderr
    engine = create_engine(f"sqlite:///{db}")
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    assert {"data_quality_jobs", "data_quality_issues", "operation_audit_logs", "quality_task_outbox"} <= tables
    assert "alembic_version" in tables


def test_migration_is_idempotent(tmp_path):
    db = tmp_path / "migrate-idempotent.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db}", "APP_ENV": "development"}
    for _ in range(2):
        result = subprocess.run(
            [sys.executable, "-m", "db.migrate", "upgrade"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 and "No module named 'alembic'" in result.stderr:
            pytest.skip("alembic is not installed (install the mysql/dev extra)")
        assert result.returncode == 0, result.stderr
