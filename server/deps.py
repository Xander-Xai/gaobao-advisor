"""Shared FastAPI dependencies."""

import os

from db.database import SessionLocal
from server.soul_query import SoulQueryEngine


def get_db():
    """Yield a SQLAlchemy session, auto-close on request end."""
    db = SessionLocal()
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
