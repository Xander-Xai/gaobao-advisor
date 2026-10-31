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
from sqlalchemy.engine import Engine

MARKER_TABLE = "_gaobao_benchmark_ownership"
_BENCH_DB_RE = re.compile(r"(benchmark|(?:^|[_-])test(?:$|[_-]))", re.IGNORECASE)


def database_name(url: str) -> str:
    return urlsplit(url).path.lstrip("/").split("/", 1)[0].split("?", 1)[0]


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


def ensure_benchmark_database(engine: Engine, url: str, *, allow_database_url_match: bool = False) -> None:
    assert_safe_benchmark_url(url, allow_database_url_match=allow_database_url_match)
    tables = set(inspect(engine).get_table_names())
    if MARKER_TABLE in tables:
        return
    if tables:
        raise RuntimeError(
            f"refusing benchmark: database {database_name(url)!r} is non-empty and has no {MARKER_TABLE} marker"
        )
    with engine.begin() as connection:
        connection.execute(text(f"CREATE TABLE {MARKER_TABLE} (id INTEGER PRIMARY KEY, owner VARCHAR(64) NOT NULL)"))
        connection.execute(text(f"INSERT INTO {MARKER_TABLE} (id, owner) VALUES (1, 'gaobao-benchmark')"))
