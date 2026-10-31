"""Detect what kind of admissions data a database actually contains.

The public demo ships only ``SYNTHETIC_DEMO_DATA`` schools. A deployment that
imports authorised real data, or a mixed database, must not keep reporting
``SYNTHETIC_DEMO`` just because that used to be the only supported profile.
"""

from __future__ import annotations

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from db.models import School

SYNTHETIC_MARKER = "SYNTHETIC_DEMO_DATA"


def detect_data_profile(session: Session) -> str:
    """Return EMPTY / SYNTHETIC_DEMO / CUSTOM / MIXED / UNKNOWN.

    ``UNKNOWN`` means the schools table could not be queried; callers must
    report it as an unknown provenance state, never as synthetic.
    """
    try:
        total, synthetic = session.query(
            func.count(School.id),
            func.coalesce(func.sum(case((School.special_type == SYNTHETIC_MARKER, 1), else_=0)), 0),
        ).one()
    except Exception:
        session.rollback()
        return "UNKNOWN"

    total = int(total or 0)
    synthetic = int(synthetic or 0)
    if total == 0:
        return "EMPTY"
    if synthetic == total:
        return "SYNTHETIC_DEMO"
    if synthetic == 0:
        return "CUSTOM"
    return "MIXED"


def current_data_profile() -> str:
    """Detect the profile through the application's default session factory."""
    from db.database import SessionLocal

    session = SessionLocal()
    try:
        return detect_data_profile(session)
    except Exception:
        return "UNKNOWN"
    finally:
        session.close()
