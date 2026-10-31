"""Safety checks for destructive benchmark database ownership."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from benchmarks.guard import (
    MARKER_TABLE,
    assert_safe_benchmark_url,
    ensure_benchmark_database,
    validate_benchmark_marker,
)

BENCH_URL = "mysql+pymysql://root:secret@127.0.0.1:3307/gaobao_benchmark?charset=utf8mb4"


def _engine_with_marker(owner: str = "gaobao-benchmark", *, rows: int = 1):
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text(f"CREATE TABLE {MARKER_TABLE} (id INTEGER PRIMARY KEY, owner VARCHAR(64) NOT NULL)"))
        for index in range(rows):
            connection.execute(
                text(f"INSERT INTO {MARKER_TABLE} (id, owner) VALUES (:id, :owner)"),
                {"id": index + 1, "owner": owner},
            )
    return engine


def test_benchmark_url_requires_dedicated_name():
    assert_safe_benchmark_url(BENCH_URL)
    with pytest.raises(RuntimeError, match="non-benchmark database"):
        assert_safe_benchmark_url("mysql+pymysql://root:secret@127.0.0.1:3307/gaobao")


def test_benchmark_url_rejects_production_match(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", BENCH_URL)
    with pytest.raises(RuntimeError, match="must not equal DATABASE_URL"):
        assert_safe_benchmark_url(BENCH_URL)
    assert_safe_benchmark_url(BENCH_URL, allow_database_url_match=True)


def test_valid_benchmark_marker_is_accepted():
    engine = _engine_with_marker()
    try:
        validate_benchmark_marker(engine)
        ensure_benchmark_database(engine, BENCH_URL)
    finally:
        engine.dispose()


def test_wrong_benchmark_owner_is_rejected():
    engine = _engine_with_marker("some-other-benchmark")
    try:
        with pytest.raises(RuntimeError, match="ownership mismatch"):
            ensure_benchmark_database(engine, BENCH_URL)
    finally:
        engine.dispose()


def test_forged_benchmark_marker_is_rejected():
    engine = _engine_with_marker(rows=2)
    try:
        with pytest.raises(RuntimeError, match="ownership mismatch"):
            validate_benchmark_marker(engine)
    finally:
        engine.dispose()


def test_non_empty_benchmark_database_without_marker_is_rejected():
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE business_data (id INTEGER PRIMARY KEY)"))
        with pytest.raises(RuntimeError, match="non-empty"):
            ensure_benchmark_database(engine, BENCH_URL)
    finally:
        engine.dispose()
