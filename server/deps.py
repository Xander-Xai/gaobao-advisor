"""Shared FastAPI dependencies."""
import os

from sqlalchemy.orm import Session

from db.database import SessionLocal


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
