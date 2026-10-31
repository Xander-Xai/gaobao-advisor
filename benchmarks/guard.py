"""Safety guard for benchmark databases.

Benchmarks create and drop their own tables. They may only run against a
dedicated database whose name contains ``benchmark`` or ``test`` and that is
either empty or carries the benchmark ownership marker.
"""

from __future__ import annotations

import os
import re
from urllib.parse import urlsplit

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine, make_url

MARKER_TABLE = "_gaobao_benchmark_ownership"
EXPECTED_OWNER = "gaobao-benchmark"
EXTRA_OWNED_TABLES = frozenset({MARKER_TABLE, "alembic_version"})
_BENCH_DB_RE = re.compile(r"(benchmark|(?:^|[_-])test(?:$|[_-]))", re.IGNORECASE)


def database_name(url: str) -> str:
    return urlsplit(url).path.lstrip("/").split("/", 1)[0].split("?", 1)[0]


def project_tables() -> frozenset[str]:
    from db.models import Base

    return frozenset(Base.metadata.tables) | EXTRA_OWNED_TABLES


def assert_safe_benchmark_url(url: str, *, allow_database_url_match: bool = False) -> None:
    if not url:
        raise RuntimeError("benchmark database URL is empty")
    if not url.startswith(("mysql://", "mysql+pymysql://")):
        raise RuntimeError("benchmark requires a MySQL URL")
    name = database_name(url)
    if not _BENCH_DB_RE.search(name):
        raise RuntimeError(f"refusing benchmark on non-benchmark database: {name!r}")
    production = os.getenv("DATABASE_URL", "").strip()
    if production and production == url and not allow_database_url_match:
        raise RuntimeError("benchmark URL must not equal DATABASE_URL")


def assert_engine_target(engine: Engine, url: str) -> None:
    """Refuse to run when the engine is connected somewhere other than ``url``."""
    expected = make_url(url)
    actual = engine.url
    if actual.get_backend_name() != expected.get_backend_name():
        raise RuntimeError(
            f"refusing benchmark: connection backend {actual.get_backend_name()!r} "
            f"does not match {expected.get_backend_name()!r}"
        )
    if actual.database != expected.database:
        raise RuntimeError(
            f"refusing benchmark: connection database {actual.database!r} does not match {expected.database!r}"
        )
    if (actual.host or "") != (expected.host or ""):
        raise RuntimeError(f"refusing benchmark: connection host {actual.host!r} does not match {expected.host!r}")
    if (actual.port or 3306) != (expected.port or 3306):
        raise RuntimeError(f"refusing benchmark: connection port {actual.port!r} does not match {expected.port!r}")


def assert_only_owned_tables(
    engine: Engine,
    *,
    allowed_tables: frozenset[str] | set[str] | None = None,
) -> None:
    allowed = project_tables() if allowed_tables is None else frozenset(allowed_tables)
    unknown = set(inspect(engine).get_table_names()) - allowed
    if unknown:
        raise RuntimeError(
            f"refusing benchmark: database contains assets outside benchmark ownership: {sorted(unknown)}"
        )


def validate_benchmark_marker(engine: Engine, *, expected_owner: str = EXPECTED_OWNER) -> None:
    """Validate the marker's schema and exact ownership record."""
    columns = {column["name"] for column in inspect(engine).get_columns(MARKER_TABLE)}
    if columns != {"id", "owner"}:
        raise RuntimeError(f"refusing benchmark: {MARKER_TABLE} has unexpected columns {sorted(columns)}")
    with engine.connect() as connection:
        rows = connection.execute(text(f"SELECT id, owner FROM {MARKER_TABLE}")).all()
    if len(rows) != 1 or rows[0][0] != 1 or rows[0][1] != expected_owner:
        raise RuntimeError(
            f"refusing benchmark: {MARKER_TABLE} ownership mismatch (expected id=1 owner={expected_owner!r})"
        )


def ensure_benchmark_database(
    engine: Engine,
    url: str,
    *,
    allow_database_url_match: bool = False,
    expected_owner: str = EXPECTED_OWNER,
    verify_target: bool = True,
    allowed_tables: frozenset[str] | set[str] | None = None,
) -> None:
    assert_safe_benchmark_url(url, allow_database_url_match=allow_database_url_match)
    if verify_target:
        assert_engine_target(engine, url)
    tables = set(inspect(engine).get_table_names())
    if MARKER_TABLE in tables:
        validate_benchmark_marker(engine, expected_owner=expected_owner)
        assert_only_owned_tables(engine, allowed_tables=allowed_tables)
        return
    if tables:
        raise RuntimeError(
            f"refusing benchmark: database {database_name(url)!r} is non-empty and has no {MARKER_TABLE} marker"
        )
    with engine.begin() as connection:
        connection.execute(text(f"CREATE TABLE {MARKER_TABLE} (id INTEGER PRIMARY KEY, owner VARCHAR(64) NOT NULL)"))
        connection.execute(text(f"INSERT INTO {MARKER_TABLE} (id, owner) VALUES (1, '{expected_owner}')"))
