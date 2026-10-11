"""Regression tests for `save_profile` slot preservation.

`save_slots` assigns `Conversation.slots_json` wholesale, but `_query_state` —
the soul-query round counter and already-asked field list — lives in that same
column and is not part of `UserProfile`. `save_profile` therefore used to
destroy it on every `PUT /api/v1/profile/{id}`, resetting the questioning state
on each edit.

Reproduced on `master` (with #8 merged):

    before PUT : {'province': ..., 'score_rank': ..., '_query_state': {...}}
    after  PUT : {'province': ..., 'score_rank': ..., 'interest': ...}
    _query_state survived PUT /profile ? -> False

Each test uses its own throw-away SQLite file; `data/gaokao.db` is never
touched.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import db.database
from db.crud import load_conversation_slots, save_slots
from db.models import Base
from server.user_profile import UserProfile, load_profile, save_profile

QUERY_STATE = {"round_count": 2, "asked_fields": ["province", "score"], "skipped_fields": []}


@pytest.fixture
def session_factory(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'profile.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    monkeypatch.setattr(db.database, "get_session", factory)
    monkeypatch.setattr(db.database, "SessionLocal", factory)
    yield factory
    engine.dispose()


def _seed(factory, session_id, slots):
    db = factory()
    try:
        save_slots(db, session_id, slots)
        db.commit()
    finally:
        db.close()


def _stored(factory, session_id):
    db = factory()
    try:
        return load_conversation_slots(db, session_id) or {}
    finally:
        db.close()


def test_save_profile_preserves_query_state(session_factory):
    sid = "save-profile-1"
    _seed(
        session_factory,
        sid,
        {
            "province": {"value": "山东", "filled": True},
            "score_rank": {"value": "620分", "filled": True},
            "_query_state": dict(QUERY_STATE),
        },
    )

    profile = load_profile(sid)
    profile.interest = "计算机"
    save_profile(sid, profile)

    assert _stored(session_factory, sid)["_query_state"] == QUERY_STATE


def test_save_profile_preserves_unrelated_slot_keys(session_factory):
    """Any key this function does not own must survive."""
    sid = "save-profile-2"
    _seed(session_factory, sid, {"province": {"value": "山东", "filled": True}, "emotion_state": "😡"})

    profile = load_profile(sid)
    profile.goal = "考研"
    save_profile(sid, profile)

    stored = _stored(session_factory, sid)
    assert stored["emotion_state"] == "😡"
    assert stored["goal"] == {"value": "考研", "filled": True}


def test_save_profile_writes_and_updates_profile_fields(session_factory):
    sid = "save-profile-3"
    _seed(
        session_factory,
        sid,
        {"province": {"value": "山东", "filled": True}, "score_rank": {"value": "620分", "filled": True}},
    )

    profile = load_profile(sid)
    profile.interest = "计算机"
    profile.score = 631
    save_profile(sid, profile)

    stored = _stored(session_factory, sid)
    assert stored["interest"] == {"value": "计算机", "filled": True}
    assert stored["score_rank"] == {"value": "631分", "filled": True}


def test_save_profile_still_removes_a_cleared_field(session_factory):
    """Merging must not make a cleared profile field immortal."""
    sid = "save-profile-4"
    _seed(
        session_factory,
        sid,
        {
            "region": {"value": "北京", "filled": True},
            "goal": {"value": "就业", "filled": True},
            "_query_state": dict(QUERY_STATE),
        },
    )

    profile = load_profile(sid)
    assert profile.region == "北京"
    profile.region = None
    save_profile(sid, profile)

    stored = _stored(session_factory, sid)
    assert "region" not in stored, "a cleared profile field must be removed"
    assert stored["goal"] == {"value": "就业", "filled": True}
    assert stored["_query_state"] == QUERY_STATE


def test_save_profile_on_new_session(session_factory):
    sid = "save-profile-5"
    profile = UserProfile()
    profile.province = "河北"
    profile.score = 600
    profile.subject = "物理"
    save_profile(sid, profile)
    stored = _stored(session_factory, sid)
    assert stored["province"] == {"value": "河北", "filled": True}
    assert stored["score_rank"] == {"value": "600分", "filled": True}


def test_profile_slot_keys_match_what_save_profile_writes(session_factory):
    """Guard: the owned-key set must cover every slot the function writes."""
    sid = "save-profile-6"
    profile = UserProfile()
    profile.province = "河北"
    profile.score = 600
    profile.subject = "物理"
    profile.interest = "计算机"
    profile.region = "北京"
    profile.family = "普通"
    profile.goal = "考研"
    save_profile(sid, profile)
    written = set(_stored(session_factory, sid)) - {"_query_state"}
    assert written <= UserProfile._PROFILE_SLOT_KEYS
    assert written == {"province", "score_rank", "subject", "interest", "region", "family", "goal"}
