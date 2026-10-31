"""Shared FastAPI dependencies."""

import os

import db.database as database
from server.soul_query import SoulQueryEngine


def get_db():
    """Yield a SQLAlchemy session, auto-close on request end.

    Resolve the session factory at call time so tests and embedders can bind
    ``db.database.SessionLocal`` to an isolated database without overriding the
    dependency in every test.
    """
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_llm_config():
    """Return LLM configuration from environment."""
    return {
        "api_base": os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "model": os.getenv("LLM_MODEL", "gpt-4o"),
    }


# ── Soul query engine singleton ───────────────────────────────────

_soul_engine: SoulQueryEngine | None = None


def get_soul_query_engine() -> SoulQueryEngine:
    """Return the singleton SoulQueryEngine."""
    global _soul_engine
    if _soul_engine is None:
        _soul_engine = SoulQueryEngine()
    return _soul_engine
