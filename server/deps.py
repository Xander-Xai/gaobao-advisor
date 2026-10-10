"""Shared FastAPI dependencies."""

from config.loader import load_llm_config
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
    cfg = load_llm_config()
    return {
        "provider": cfg.get("provider"),
        "api_base": cfg.get("base_url"),
        "api_key": cfg.get("api_key"),
        "model": cfg.get("model"),
    }


# ── Soul query engine singleton ───────────────────────────────────

_soul_engine: SoulQueryEngine | None = None


def get_soul_query_engine() -> SoulQueryEngine:
    """Return the singleton SoulQueryEngine."""
    global _soul_engine
    if _soul_engine is None:
        _soul_engine = SoulQueryEngine()
    return _soul_engine
