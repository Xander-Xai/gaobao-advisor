"""Alembic migration entry point.

Usage::

    python -m db.migrate              # upgrade to head
    python -m db.migrate current      # show current revision
    python -m db.migrate history

The URL comes from ``DATABASE_URL`` through ``db.database``. No credentials are
stored in ``alembic.ini``.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine

from db.database import DATABASE_URL, redact_database_url
from db.schema_contract import BASELINE_TABLES, verify_tables

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent


def alembic_config() -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    # Keep credentials out of the generated config; env.py reads DATABASE_URL.
    config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))
    return config


def upgrade_head() -> None:
    logger.info("running migrations against %s", redact_database_url(DATABASE_URL))
    command.upgrade(alembic_config(), "head")


def adopt_existing() -> None:
    """Adopt an already-created schema into Alembic without recreating tables.

    This is an explicit, non-destructive DBA command for databases previously
    bootstrapped by ``Base.metadata.create_all`` (legacy demo/full profile).
    It verifies all 18 tables against the schema contract before stamping the
    admin baseline revision. It never drops or creates a table.
    """
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    try:
        problems = verify_tables(engine, BASELINE_TABLES)
        if problems:
            raise RuntimeError("existing schema cannot be adopted; fix these mismatches first: " + "; ".join(problems))
        with engine.connect() as connection:
            current = MigrationContext.configure(connection).get_current_revision()
        if current == "20261031_0002":
            logger.info("database is already at head; nothing to adopt")
            return
        if current not in (None, "20261030_0001"):
            raise RuntimeError(f"refusing to stamp from unexpected revision {current!r}")
        if current is None:
            command.stamp(alembic_config(), "20261030_0001")
        logger.info("adopted existing schema at revision 20261030_0001; run upgrade head for 0002")
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Database migrations")
    parser.add_argument(
        "action",
        nargs="?",
        default="upgrade",
        choices=["upgrade", "current", "history", "heads", "adopt-existing"],
    )
    args = parser.parse_args(argv)
    cfg = alembic_config()
    if args.action == "upgrade":
        command.upgrade(cfg, "head")
    elif args.action == "adopt-existing":
        adopt_existing()
    elif args.action == "current":
        command.current(cfg)
    elif args.action == "history":
        command.history(cfg)
    else:
        command.heads(cfg)
    return 0


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
