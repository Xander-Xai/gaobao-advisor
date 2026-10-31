"""Safety checks for destructive MySQL test URLs."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from tests.mysql_guard import MARKER_TABLE, assert_safe_test_url, ensure_test_database, validate_test_marker


def test_accepts_dedicated_test_database_name():
    assert_safe_test_url("mysql+pymysql://root:secret@127.0.0.1:3307/gaobao_test?charset=utf8mb4")


def test_rejects_non_test_database_name():
    with pytest.raises(RuntimeError, match="non-test database"):
        assert_safe_test_url("mysql+pymysql://root:secret@127.0.0.1:3307/gaobao")


def test_rejects_database_url_equal_to_production_url(monkeypatch):
    url = "mysql+pymysql://root:secret@127.0.0.1:3307/gaobao_test?charset=utf8mb4"
    monkeypatch.setenv("DATABASE_URL", url)
    with pytest.raises(RuntimeError, match="must not equal DATABASE_URL"):
        assert_safe_test_url(url)


def test_rejects_non_mysql_url():
    with pytest.raises(RuntimeError, match="must be a MySQL URL"):
        assert_safe_test_url("sqlite:///data/gaobao_test.db")


MYSQL_TEST_URL = "mysql+pymysql://root:secret@127.0.0.1:3307/gaobao_test?charset=utf8mb4"


def _engine_with_marker(owner: str = "gaobao-test-suite", *, rows: int = 1):
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text(f"CREATE TABLE {MARKER_TABLE} (id INTEGER PRIMARY KEY, owner VARCHAR(64) NOT NULL)"))
        for index in range(rows):
            connection.execute(
                text(f"INSERT INTO {MARKER_TABLE} (id, owner) VALUES (:id, :owner)"),
                {"id": index + 1, "owner": owner},
            )
    return engine


def test_valid_marker_is_accepted():
    engine = _engine_with_marker()
    try:
        validate_test_marker(engine)
        ensure_test_database(engine, MYSQL_TEST_URL)
    finally:
        engine.dispose()


def test_wrong_owner_marker_is_rejected():
    engine = _engine_with_marker("some-other-suite")
    try:
        with pytest.raises(RuntimeError, match="ownership mismatch"):
            ensure_test_database(engine, MYSQL_TEST_URL)
    finally:
        engine.dispose()


def test_forged_marker_with_multiple_rows_is_rejected():
    engine = _engine_with_marker(rows=2)
    try:
        with pytest.raises(RuntimeError, match="ownership mismatch"):
            validate_test_marker(engine)
    finally:
        engine.dispose()


def test_marker_with_wrong_schema_is_rejected():
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.execute(text(f"CREATE TABLE {MARKER_TABLE} (id INTEGER PRIMARY KEY, note VARCHAR(64))"))
        with pytest.raises(RuntimeError, match="unexpected columns"):
            validate_test_marker(engine)
    finally:
        engine.dispose()


def test_non_empty_database_without_marker_is_rejected():
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE business_data (id INTEGER PRIMARY KEY)"))
        with pytest.raises(RuntimeError, match="non-empty"):
            ensure_test_database(engine, MYSQL_TEST_URL)
    finally:
        engine.dispose()


def test_marker_allows_other_test_tables():
    engine = _engine_with_marker()
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE test_payload (id INTEGER PRIMARY KEY)"))
        ensure_test_database(engine, MYSQL_TEST_URL)
    finally:
        engine.dispose()
