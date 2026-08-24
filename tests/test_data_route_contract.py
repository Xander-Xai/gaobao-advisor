"""Regression tests for data route filtering and cursor validation."""

import uuid

from fastapi.testclient import TestClient

from db.database import SessionLocal, init_db
from db.models import AdmissionScore, Major, School
from server.main import app

client = TestClient(app)


def test_scores_rejects_malformed_cursor_before_querying_database():
    response = client.get(
        "/api/v1/data/scores",
        params={
            "school_name": "不存在也没关系",
            "province": "河北",
            "cursor": "not-an-integer",
        },
    )
    assert response.status_code == 422


def test_plans_rejects_negative_cursor():
    response = client.get(
        "/api/v1/data/plans",
        params={"school_name": "不存在也没关系", "cursor": -1},
    )
    assert response.status_code == 422


def test_scores_filters_major_by_related_major_name():
    """The `major` parameter filters Major.name instead of comparing a relationship to str."""
    init_db()
    suffix = uuid.uuid4().hex[:10]
    school_name = f"测试大学-{suffix}"
    target_major_name = f"测试专业A-{suffix}"
    other_major_name = f"测试专业B-{suffix}"

    db = SessionLocal()
    school = None
    target_major = None
    other_major = None
    try:
        school = School(name=school_name, province="河北", city="测试市")
        target_major = Major(name=target_major_name, category="工学")
        other_major = Major(name=other_major_name, category="工学")
        db.add_all([school, target_major, other_major])
        db.commit()
        db.refresh(school)
        db.refresh(target_major)
        db.refresh(other_major)

        db.add_all(
            [
                AdmissionScore(
                    school_id=school.id,
                    major_id=target_major.id,
                    province="河北",
                    year=2025,
                    subject_type="物理",
                    min_score=600,
                ),
                AdmissionScore(
                    school_id=school.id,
                    major_id=other_major.id,
                    province="河北",
                    year=2025,
                    subject_type="物理",
                    min_score=580,
                ),
            ]
        )
        db.commit()

        response = client.get(
            "/api/v1/data/scores",
            params={
                "school_name": school_name,
                "province": "河北",
                "year": 2025,
                "major": target_major_name,
            },
        )
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["major"] == target_major_name
        assert items[0]["min_score"] == 600
    finally:
        if school is not None:
            db.query(AdmissionScore).filter(AdmissionScore.school_id == school.id).delete(
                synchronize_session=False
            )
            db.delete(school)
        if target_major is not None:
            db.delete(target_major)
        if other_major is not None:
            db.delete(other_major)
        db.commit()
        db.close()
