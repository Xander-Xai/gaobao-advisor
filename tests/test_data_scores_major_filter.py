"""Regression tests for GET /api/v1/data/scores filtering and projection.

Background
----------
``AdmissionScore.major`` is an ORM *relationship* to :class:`Major`, while the
query parameter ``major`` carries a **major name**. Comparing the relationship
attribute against a plain string raises ``sqlalchemy.exc.ArgumentError``
("Mapped instance expected for relationship comparison to object"), so a
perfectly valid request such as::

    GET /api/v1/data/scores?school_name=中国政法大学&province=北京&major=法学

could never return the matching rows.

Every test below runs against a throw-away SQLite database; the developer's
``data/gaokao.db`` is never read or written.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import db.database
from db.models import AdmissionScore, Base, Major, School
from server.main import app

SCHOOL = "中国政法大学"
PROVINCE = "北京"


@pytest.fixture
def session_factory(tmp_path, monkeypatch):
    """Point ``db.database.SessionLocal`` at an isolated per-test SQLite file."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'scores.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    monkeypatch.setattr(db.database, "SessionLocal", factory)
    yield factory
    engine.dispose()


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


def _seed(session_factory):
    """Seed two majors and five score rows for :data:`SCHOOL`.

    Rows:
      1. 法学      -> min/avg/max score + rank all populated
      2. 计算机    -> rank is NULL (rank not published for this row)
      3. None      -> school-level line, no major attached
      4. dangling  -> major_id points at a majors row that does not exist
      5. 法学/other-> same major name, different province + year (must not leak)
    """
    db = session_factory()
    try:
        school = School(name=SCHOOL, province=PROVINCE, city=PROVINCE)
        law = Major(name="法学", category="法学")
        cs = Major(name="计算机", category="工学")
        db.add_all([school, law, cs])
        db.commit()
        db.refresh(school)
        db.refresh(law)
        db.refresh(cs)

        rows = [
            # 1: fully populated
            AdmissionScore(
                school_id=school.id,
                major_id=law.id,
                province=PROVINCE,
                year=2024,
                batch="本科一批",
                subject_type="综合",
                min_score=640,
                avg_score=645.5,
                max_score=651,
                min_rank=120,
            ),
            # 2: rank missing
            AdmissionScore(
                school_id=school.id,
                major_id=cs.id,
                province=PROVINCE,
                year=2024,
                batch="本科一批",
                subject_type="综合",
                min_score=600,
                avg_score=None,
                max_score=None,
                min_rank=None,
            ),
            # 3: school-level line, major_id NULL
            AdmissionScore(
                school_id=school.id,
                major_id=None,
                province=PROVINCE,
                year=2024,
                batch="本科一批",
                subject_type="综合",
                min_score=585,
                avg_score=590.0,
                max_score=598,
                min_rank=3000,
            ),
            # 4: dangling foreign key (SQLite does not enforce FK by default)
            AdmissionScore(
                school_id=school.id,
                major_id=law.id + 9000,
                province=PROVINCE,
                year=2024,
                batch="本科一批",
                subject_type="综合",
                min_score=500,
                avg_score=None,
                max_score=None,
                min_rank=None,
            ),
            # 5: must never appear in PROVINCE/2024 results
            AdmissionScore(
                school_id=school.id,
                major_id=law.id,
                province="河北",
                year=2023,
                batch="本科一批",
                subject_type="综合",
                min_score=610,
                avg_score=None,
                max_score=None,
                min_rank=None,
            ),
        ]
        db.add_all(rows)
        db.commit()
        return {
            "school_id": school.id,
            "law_major_id": law.id,
            "cs_major_id": cs.id,
            "ids": [r.id for r in rows],
        }
    finally:
        db.close()


# ── 1. school_name + major joint filter (the reported defect) ────────────────


@pytest.mark.asyncio
async def test_scores_filters_by_major_name(session_factory, client):
    """The reported request must return the 法学 row and nothing else."""
    _seed(session_factory)
    async with client as c:
        response = await c.get(
            "/api/v1/data/scores",
            params={"school_name": SCHOOL, "province": PROVINCE, "major": "法学"},
        )
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["major"] == "法学"
    assert items[0]["school_name"] == SCHOOL
    assert items[0]["min_score"] == 640


@pytest.mark.asyncio
async def test_scores_major_filter_composes_with_year(session_factory, client):
    """Adding `year` must narrow the result set instead of widening it."""
    _seed(session_factory)
    async with client as c:
        response = await c.get(
            "/api/v1/data/scores",
            params={
                "school_name": SCHOOL,
                "province": PROVINCE,
                "year": 2024,
                "major": "法学",
            },
        )
    assert response.status_code == 200
    assert [i["year"] for i in response.json()["items"]] == [2024]


# ── 2. school_name only ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_scores_without_major_returns_every_row_for_school(session_factory, client):
    """Omitting `major` keeps the unfiltered behaviour (4 rows in PROVINCE)."""
    _seed(session_factory)
    async with client as c:
        response = await c.get(
            "/api/v1/data/scores",
            params={"school_name": SCHOOL, "province": PROVINCE},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["has_more"] is False
    assert body["next_cursor"] is None
    assert len(body["items"]) == 4


@pytest.mark.asyncio
async def test_scores_unknown_school_returns_empty_page(session_factory, client):
    async with client as c:
        response = await c.get(
            "/api/v1/data/scores",
            params={"school_name": "不存在的学校", "province": PROVINCE},
        )
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None, "has_more": False}


# ── 3. unknown major ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_scores_unknown_major_returns_empty_page(session_factory, client):
    """An unmatched major name is a valid filter that matches nothing."""
    _seed(session_factory)
    async with client as c:
        response = await c.get(
            "/api/v1/data/scores",
            params={"school_name": SCHOOL, "province": PROVINCE, "major": "考古学"},
        )
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.asyncio
async def test_scores_major_filter_is_exact_not_substring(session_factory, client):
    """`major=法` must not match the major named `法学`."""
    _seed(session_factory)
    async with client as c:
        response = await c.get(
            "/api/v1/data/scores",
            params={"school_name": SCHOOL, "province": PROVINCE, "major": "法"},
        )
    assert response.status_code == 200
    assert response.json()["items"] == []


# ── 4. rows without a resolvable Major ───────────────────────────────────────


@pytest.mark.asyncio
async def test_scores_rows_without_major_are_reported_without_major_key(session_factory, client):
    """`major_id IS NULL` rows stay visible unfiltered and carry no `major`."""
    _seed(session_factory)
    async with client as c:
        response = await c.get(
            "/api/v1/data/scores",
            params={"school_name": SCHOOL, "province": PROVINCE},
        )
    items = response.json()["items"]
    school_level = [i for i in items if "major" not in i]
    assert len(school_level) == 2  # major_id NULL + dangling major_id
    assert {i["min_score"] for i in school_level} == {585, 500}


@pytest.mark.asyncio
async def test_scores_dangling_major_id_does_not_break_major_filter(session_factory, client):
    """A row pointing at a deleted majors row must not break the join."""
    _seed(session_factory)
    async with client as c:
        response = await c.get(
            "/api/v1/data/scores",
            params={"school_name": SCHOOL, "province": PROVINCE, "major": "法学"},
        )
    assert response.status_code == 200
    assert [i["min_score"] for i in response.json()["items"]] == [640]


# ── 5. major id <-> name mapping ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_major_name_resolves_to_expected_major_id(session_factory, client):
    """Each name must resolve to exactly one major id, and scores follow it."""
    seeded = _seed(session_factory)
    db = session_factory()
    try:
        assert db.query(Major).filter(Major.name == "法学").one().id == seeded["law_major_id"]
        assert db.query(Major).filter(Major.name == "计算机").one().id == seeded["cs_major_id"]
    finally:
        db.close()

    async with client as c:
        law_resp = await c.get(
            "/api/v1/data/scores",
            params={"school_name": SCHOOL, "province": PROVINCE, "major": "法学"},
        )
        cs_resp = await c.get(
            "/api/v1/data/scores",
            params={"school_name": SCHOOL, "province": PROVINCE, "major": "计算机"},
        )
    assert [i["major"] for i in law_resp.json()["items"]] == ["法学"]
    assert [i["major"] for i in cs_resp.json()["items"]] == ["计算机"]


@pytest.mark.asyncio
async def test_major_filter_does_not_cross_school_or_province(session_factory, client):
    """Rows 5 (other province/year) must not leak into a filtered result."""
    _seed(session_factory)
    async with client as c:
        response = await c.get(
            "/api/v1/data/scores",
            params={"school_name": SCHOOL, "province": PROVINCE, "major": "法学"},
        )
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["province"] == PROVINCE
    assert items[0]["year"] == 2024


# ── 6. score / rank projection: valid, missing, abnormal ─────────────────────


@pytest.mark.asyncio
async def test_scores_project_score_and_rank_values(session_factory, client):
    """Valid values, NULL rank, NULL averages all survive the projection."""
    _seed(session_factory)
    async with client as c:
        law = await c.get(
            "/api/v1/data/scores",
            params={"school_name": SCHOOL, "province": PROVINCE, "major": "法学"},
        )
        cs = await c.get(
            "/api/v1/data/scores",
            params={"school_name": SCHOOL, "province": PROVINCE, "major": "计算机"},
        )

    law_item = law.json()["items"][0]
    assert law_item["min_score"] == 640
    assert law_item["avg_score"] == pytest.approx(645.5)
    assert law_item["max_score"] == 651
    assert law_item["min_rank"] == 120

    cs_item = cs.json()["items"][0]
    assert cs_item["min_score"] == 600
    assert cs_item["avg_score"] is None
    assert cs_item["max_score"] is None
    assert cs_item["min_rank"] is None


@pytest.mark.asyncio
async def test_scores_pass_through_out_of_domain_score_values(session_factory, client):
    """The endpoint projects stored numbers verbatim and must not crash on them."""
    db = session_factory()
    try:
        db.add(
            AdmissionScore(
                school_id=_seed(session_factory)["school_id"],
                major_id=None,
                province=PROVINCE,
                year=2024,
                batch="本科一批",
                subject_type="综合",
                min_score=-1,
                avg_score=99999.5,
                max_score=0,
                min_rank=-42,
            )
        )
        db.commit()
    finally:
        db.close()

    async with client as c:
        response = await c.get(
            "/api/v1/data/scores",
            params={"school_name": SCHOOL, "province": PROVINCE},
        )
    assert response.status_code == 200
    weird = [i for i in response.json()["items"] if i["min_score"] == -1]
    assert len(weird) == 1
    assert weird[0]["avg_score"] == pytest.approx(99999.5)
    assert weird[0]["min_rank"] == -42


@pytest.mark.asyncio
async def test_scores_all_null_score_fields(session_factory, client):
    """A row with every score/rank column NULL still serialises to nulls."""
    db = session_factory()
    try:
        db.add(
            AdmissionScore(
                school_id=_seed(session_factory)["school_id"],
                major_id=None,
                province=PROVINCE,
                year=2024,
                batch="本科一批",
                subject_type="综合",
            )
        )
        db.commit()
    finally:
        db.close()

    async with client as c:
        response = await c.get(
            "/api/v1/data/scores",
            params={"school_name": SCHOOL, "province": PROVINCE},
        )
    assert response.status_code == 200
    empty = [i for i in response.json()["items"] if i["min_score"] is None]
    assert len(empty) == 1
    assert empty[0]["avg_score"] is None
    assert empty[0]["max_score"] is None
    assert empty[0]["min_rank"] is None


# ── 7. ORM query and API response agree ──────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("major_name", [None, "法学", "计算机", "考古学"])
async def test_api_matches_direct_orm_query(session_factory, client, major_name):
    """The API projection must equal the equivalent hand-written ORM query."""
    _seed(session_factory)
    db = session_factory()
    try:
        query = db.query(AdmissionScore).filter(
            AdmissionScore.school_id == _school_id(db),
            AdmissionScore.province == PROVINCE,
        )
        if major_name is not None:
            query = query.join(Major, AdmissionScore.major_id == Major.id).filter(Major.name == major_name)
        expected = [
            {
                "id": row.id,
                "school_name": SCHOOL,
                "province": row.province,
                "year": row.year,
                "batch": row.batch,
                "subject_type": row.subject_type,
                "min_score": row.min_score,
                "avg_score": row.avg_score,
                "max_score": row.max_score,
                "min_rank": row.min_rank,
                "major": row.major.name if row.major else None,
            }
            for row in query.order_by(AdmissionScore.id).all()
        ]
    finally:
        db.close()

    params = {"school_name": SCHOOL, "province": PROVINCE}
    if major_name is not None:
        params["major"] = major_name
    async with client as c:
        response = await c.get("/api/v1/data/scores", params=params)
    assert response.status_code == 200

    normalised = list(response.json()["items"])
    assert len(normalised) == len(expected)
    for got, want in zip(normalised, expected, strict=True):
        for key, value in want.items():
            if key == "major" and value is None:
                assert key not in got
            else:
                assert got.get(key) == value


def _school_id(session):
    return session.query(School).filter(School.name == SCHOOL).one().id
