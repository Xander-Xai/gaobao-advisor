"""Pagination cursors must be validated, never turned into HTTP 500s."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import db.database
from db.database import Base
from server.main import app
from server.routes.data import _parse_cursor
from tests.conftest import _seed


@pytest.fixture
def data_factory(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'data-cursor.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    session = factory()
    try:
        _seed(session)
    finally:
        session.close()
    monkeypatch.setattr(db.database, "SessionLocal", factory)
    yield factory
    engine.dispose()


@pytest.mark.parametrize("value", ["not-an-int", "-1", "1.5", " 1", "1e3", "0x10", "9" * 20])
def test_parse_cursor_rejects_malformed_values(value):
    with pytest.raises(Exception) as exc:
        _parse_cursor(value)
    assert getattr(exc.value, "status_code", None) == 400


def test_parse_cursor_accepts_empty_and_positive_int():
    assert _parse_cursor(None) is None
    assert _parse_cursor("") is None
    assert _parse_cursor("0") == 0
    assert _parse_cursor("42") == 42


def test_schools_cursor_is_validated(data_factory):
    client = TestClient(app)
    response = client.get("/api/v1/data/schools", params={"cursor": "not-an-int"})
    assert response.status_code == 400
    assert "cursor" in response.json()["detail"].lower()

    valid = client.get("/api/v1/data/schools", params={"limit": 2})
    assert valid.status_code == 200
    assert valid.json()["items"]


def test_scores_and_plans_reject_bad_cursor_before_early_return(data_factory):
    client = TestClient(app)
    school = "北辰示例科技大学（合成）"
    for path in ("/api/v1/data/scores", "/api/v1/data/plans"):
        response = client.get(path, params={"school_name": school, "province": "示例省·甲", "cursor": "bad"})
        assert response.status_code == 400, (path, response.text)
    # An unknown school must not hide the malformed cursor either.
    response = client.get(
        "/api/v1/data/scores",
        params={"school_name": "不存在的院校", "province": "示例省·甲", "cursor": "bad"},
    )
    assert response.status_code == 400


def test_valid_cursor_still_paginates(data_factory):
    client = TestClient(app)
    first = client.get("/api/v1/data/schools", params={"limit": 2}).json()
    assert first["has_more"] is True
    second = client.get("/api/v1/data/schools", params={"limit": 2, "cursor": first["next_cursor"]}).json()
    assert second["items"]
    assert {item["id"] for item in first["items"]}.isdisjoint({item["id"] for item in second["items"]})
