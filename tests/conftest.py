"""Shared fixtures for the administrator workbench tests."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base
from db.models import (  # noqa: F401 - register all tables on Base.metadata
    AdmissionScore,
    DataQualityIssue,
    DataQualityJob,
    EnrollmentPlan,
    Major,
    OperationAuditLog,
    QualityTaskOutbox,
    School,
    SubjectRanking,
)
from scripts.seed_demo_data import build_payload
from server.admin.auth import hash_password
from server.admin.routes import _job_limiter, _login_limiter
from server.deps import get_db
from server.main import app

ADMIN_PASSWORD = "Demo-Admin-Pass-2026!"
PASSWORD_HASH = hash_password(ADMIN_PASSWORD, iterations=10_000)


def _users_json() -> str:
    return json.dumps(
        [
            {"username": "viewer", "password_hash": PASSWORD_HASH, "role": "viewer"},
            {"username": "operator", "password_hash": PASSWORD_HASH, "role": "operator"},
            {"username": "admin", "password_hash": PASSWORD_HASH, "role": "admin"},
        ]
    )


@pytest.fixture
def admin_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ADMIN_USERS_JSON", _users_json())
    monkeypatch.setenv("ADMIN_TOKEN_SECRET", "test-admin-token-secret-" + "x" * 40)
    monkeypatch.setenv("QUALITY_TASK_MODE", "inline")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("ADMIN_ENABLED", raising=False)
    _login_limiter.reset()
    _job_limiter.reset()
    yield {"password": ADMIN_PASSWORD}
    _login_limiter.reset()
    _job_limiter.reset()


def _seed(session) -> None:
    payload = build_payload()
    schools = [School(**row) for row in payload["schools"]]
    majors = [Major(**row) for row in payload["majors"]]
    session.add_all(schools)
    session.add_all(majors)
    session.flush()
    session.add_all(
        [
            AdmissionScore(
                school_id=schools[row["school_idx"]].id,
                major_id=majors[row["major_idx"]].id,
                province=row["province"],
                year=row["year"],
                batch=row["batch"],
                standardized_batch=row["standardized_batch"],
                subject_type=row["subject_type"],
                min_score=row["min_score"],
                avg_score=row["avg_score"],
                max_score=row["max_score"],
                min_rank=row["min_rank"],
                plan_count=row["plan_count"],
            )
            for row in payload["admission_scores"]
        ]
    )
    session.add_all(
        [
            EnrollmentPlan(
                school_id=schools[row["school_idx"]].id,
                major_id=majors[row["major_idx"]].id,
                province=row["province"],
                year=row["year"],
                plan_count=row["plan_count"],
                subject_requirement=row["subject_requirement"],
                batch=row["batch"],
                duration=row["duration"],
                tuition=row["tuition"],
            )
            for row in payload["enrollment_plans"]
        ]
    )
    session.add_all(
        [
            SubjectRanking(
                school_id=schools[row["school_idx"]].id,
                major_category=row["major_category"],
                ranking_source=row["ranking_source"],
                ranking_year=row["ranking_year"],
                ranking_position=row["ranking_position"],
                grade=row["grade"],
            )
            for row in payload["subject_rankings"]
        ]
    )
    # Deliberate anomalies so the quality job produces deterministic findings.
    session.add(
        AdmissionScore(
            school_id=schools[0].id,
            major_id=majors[0].id,
            province="示例省·甲",
            year=2099,
            batch="本科批",
            subject_type="物理类",
            min_score=900,
            avg_score=800,
            max_score=700,
            min_rank=0,
            plan_count=10,
        )
    )
    session.add(
        EnrollmentPlan(
            school_id=schools[0].id,
            major_id=majors[1].id,
            province="示例省·甲",
            year=2099,
            plan_count=0,
            subject_requirement="不限",
            batch="本科批",
            duration=4,
            tuition=300_000,
        )
    )
    session.commit()


@pytest.fixture
def admin_factory(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'admin-test.db'}",
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = factory()
    try:
        _seed(session)
    finally:
        session.close()
    yield factory
    engine.dispose()


@pytest.fixture
def admin_client(admin_env, admin_factory):
    def override_get_db():
        session = admin_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        client.close()


def login(client: TestClient, username: str = "admin", password: str = ADMIN_PASSWORD) -> str:
    response = client.post("/api/v1/admin/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
