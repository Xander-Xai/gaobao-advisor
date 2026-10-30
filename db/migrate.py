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

from db.database import DATABASE_URL, redact_database_url

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Database migrations")
    parser.add_argument("action", nargs="?", default="upgrade", choices=["upgrade", "current", "history", "heads"])
    args = parser.parse_args(argv)
    cfg = alembic_config()
    if args.action == "upgrade":
        command.upgrade(cfg, "head")
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
