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


def ensure_test_database(engine: Engine, url: str) -> None:
    """Validate ownership and create the marker on an empty test database."""
    assert_safe_test_url(url)
    tables = set(inspect(engine).get_table_names())
    if MARKER_TABLE in tables:
        return
    if tables:
        raise RuntimeError(
            f"refusing destructive test: database {_database_name(url)!r} is non-empty "
            f"and has no {MARKER_TABLE} ownership marker"
        )
    with engine.begin() as connection:
        connection.execute(text(f"CREATE TABLE {MARKER_TABLE} (id INTEGER PRIMARY KEY, owner VARCHAR(64) NOT NULL)"))
        connection.execute(text(f"INSERT INTO {MARKER_TABLE} (id, owner) VALUES (1, 'gaobao-test-suite')"))
