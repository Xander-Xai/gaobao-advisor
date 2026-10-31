"""Data provenance detection must reflect the rows, not a constant."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base
from db.models import School
from server.services.data_profile import SYNTHETIC_MARKER, detect_data_profile


def _factory():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False)


def test_empty_database_is_empty():
    session = _factory()()
    try:
        assert detect_data_profile(session) == "EMPTY"
    finally:
        session.close()


def test_all_synthetic_rows_are_synthetic_demo():
    session = _factory()()
    try:
        session.add_all(
            [
                School(name="合成甲", province="示例省", special_type=SYNTHETIC_MARKER),
                School(name="合成乙", province="示例省", special_type=SYNTHETIC_MARKER),
            ]
        )
        session.commit()
        assert detect_data_profile(session) == "SYNTHETIC_DEMO"
    finally:
        session.close()


def test_all_real_rows_are_custom():
    session = _factory()()
    try:
        session.add(School(name="某真实院校", province="某省", special_type=None))
        session.commit()
        assert detect_data_profile(session) == "CUSTOM"
    finally:
        session.close()


def test_mixed_rows_are_not_reported_as_synthetic():
    session = _factory()()
    try:
        session.add_all(
            [
                School(name="合成", province="示例省", special_type=SYNTHETIC_MARKER),
                School(name="真实", province="某省", special_type=None),
            ]
        )
        session.commit()
        assert detect_data_profile(session) == "MIXED"
    finally:
        session.close()


def test_unqueryable_table_is_unknown_not_synthetic():
    engine = create_engine("sqlite://")
    session = sessionmaker(bind=engine)()
    try:
        assert detect_data_profile(session) == "UNKNOWN"
    finally:
        session.close()
