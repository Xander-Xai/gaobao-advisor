"""Safety guard for destructive MySQL integration tests.

A database is considered disposable only when both conditions hold:

1. the URL database name matches the dedicated test naming convention; and
2. the database is empty, or already contains our ownership marker table.

The marker is created by the test suite itself. A non-empty database without
the marker is rejected before any DROP/CREATE. This prevents a mis-pointed
``MYSQL_TEST_URL`` from deleting a business schema even if its name contains
"test".
"""

from __future__ import annotations

import os
import re
from urllib.parse import urlsplit

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

MARKER_TABLE = "_gaobao_test_ownership"
EXPECTED_OWNER = "gaobao-test-suite"
_TEST_DB_RE = re.compile(r"(?:^|[_-])test(?:$|[_-])", re.IGNORECASE)


def _database_name(url: str) -> str:
    return urlsplit(url).path.lstrip("/").split("/", 1)[0].split("?", 1)[0]


def assert_safe_test_url(url: str) -> None:
    if not url:
        raise RuntimeError("MYSQL_TEST_URL is empty; refusing destructive test")
    if not url.startswith(("mysql://", "mysql+pymysql://")):
        raise RuntimeError("MYSQL_TEST_URL must be a MySQL URL")
    name = _database_name(url)
    if not _TEST_DB_RE.search(name):
        raise RuntimeError(f"refusing destructive test on non-test database name: {name!r}")
    production = os.getenv("DATABASE_URL", "").strip()
    if production and production == url:
        raise RuntimeError("MYSQL_TEST_URL must not equal DATABASE_URL; refusing destructive test")


def validate_test_marker(engine: Engine, *, expected_owner: str = EXPECTED_OWNER) -> None:
    """Validate the marker's schema and exact ownership record.

    A same-named table is not enough: a mis-pointed database can contain a
    forged/old marker. Require exactly one row with id=1 and the expected owner.
    """
    columns = {column["name"] for column in inspect(engine).get_columns(MARKER_TABLE)}
    if columns != {"id", "owner"}:
        raise RuntimeError(f"refusing destructive test: {MARKER_TABLE} has unexpected columns {sorted(columns)}")
    with engine.connect() as connection:
        rows = connection.execute(text(f"SELECT id, owner FROM {MARKER_TABLE}")).all()
    if len(rows) != 1 or rows[0][0] != 1 or rows[0][1] != expected_owner:
        raise RuntimeError(
            f"refusing destructive test: {MARKER_TABLE} ownership mismatch (expected id=1 owner={expected_owner!r})"
        )


def ensure_test_database(engine: Engine, url: str, *, expected_owner: str = EXPECTED_OWNER) -> None:
    """Validate ownership and create the marker on an empty test database."""
    assert_safe_test_url(url)
    tables = set(inspect(engine).get_table_names())
    if MARKER_TABLE in tables:
        validate_test_marker(engine, expected_owner=expected_owner)
        return
    if tables:
        raise RuntimeError(
            f"refusing destructive test: database {_database_name(url)!r} is non-empty "
            f"and has no {MARKER_TABLE} ownership marker"
        )
    with engine.begin() as connection:
        connection.execute(text(f"CREATE TABLE {MARKER_TABLE} (id INTEGER PRIMARY KEY, owner VARCHAR(64) NOT NULL)"))
        connection.execute(text(f"INSERT INTO {MARKER_TABLE} (id, owner) VALUES (1, '{expected_owner}')"))
