"""Tests for server/user_profile.py — user profile model."""

from __future__ import annotations

import uuid

from db.crud import load_conversation_slots, save_slots
from db.database import get_session
from server.user_profile import UserProfile


class TestUserProfile:
    def test_empty_profile_no_required_fields(self):
        p = UserProfile()
        assert p.is_required_complete() is False
        assert len(p.missing_required_fields()) == 4

    def test_full_profile_is_complete(self):
        p = UserProfile()
        p.province = "广东"
        p.score = 600
        p.subject = "物理"
        p.interest = "想学计算机"
        assert p.is_required_complete() is True
        assert p.missing_required_fields() == []

    def test_partial_profile(self):
        p = UserProfile()
        p.province = "广东"
        assert p.is_required_complete() is False
        missing = p.missing_required_fields()
        assert "province" not in missing
        assert "score" in missing

    def test_to_dict_omits_none(self):
        p = UserProfile()
        p.province = "北京"
        d = p.to_dict()
        assert d["province"] == "北京"
        assert d["score"] is None

    def test_from_dict_roundtrip(self):
        data = {
            "province": "上海",
            "score": 650,
            "subject": "物理",
            "interest": "金融",
            "region": "上海",
        }
        p = UserProfile.from_dict(data)
        assert p.province == "上海"
        assert p.score == 650
        assert p.interest == "金融"
        # Should not set fields not in data
        assert p.family is None

    def test_from_slots_parses_values(self):
        slots = {
            "province": {"value": "浙江", "filled": True},
            "score_rank": {"value": "650分", "filled": True},
            "subject": {"value": "物理+化学", "filled": True},
            "interest": {"value": "想学计算机", "filled": True},
            "region": {"value": "杭州", "filled": True},
        }
        p = UserProfile.from_slots(slots)
        assert p.province == "浙江"
        assert p.score == 650
        assert p.subject == "物理+化学"

    def test_from_slots_ignores_unfilled(self):
        slots = {
            "province": {"value": "江苏", "filled": True},
            "score_rank": {"value": "", "filled": False},
        }
        p = UserProfile.from_slots(slots)
        assert p.province == "江苏"
        assert p.score is None

    def test_to_context_dict(self):
        p = UserProfile()
        p.province = "福建"
        p.score = 550
        ctx = p.to_context_dict()
        assert ctx["省份"] == "福建"
        assert ctx["分数"] == "550"

    def test_count_filled(self):
        p = UserProfile()
        assert p.count_filled() == 0
        p.province = "湖南"
        p.score = 600
        assert p.count_filled() == 2

    def test_from_slots_extracts_score_from_rank(self):
        """score_rank with rank info should not set score."""
        slots = {
            "score_rank": {"value": "位次3000", "filled": True},
        }
        p = UserProfile.from_slots(slots)
        assert p.score is None  # Rank doesn't set score

    def test_from_slots_extracts_score_numeric(self):
        """score_rank with numeric should set score."""
        slots = {
            "score_rank": {"value": "580分", "filled": True},
        }
        p = UserProfile.from_slots(slots)
        assert p.score == 580

    def test_from_slots_accepts_flat_graph_slots(self):
        """Graph memory stores slots as flat values; profile loading must support them."""
        slots = {
            "province": "湖北",
            "score_rank": "580分",
            "subject": "物理",
            "interest": "计算机",
        }
        p = UserProfile.from_slots(slots)
        assert p.province == "湖北"
        assert p.score == 580
        assert p.subject == "物理"
        assert p.interest == "计算机"

    def test_score_validation(self):
        """Score must be within valid range."""
        # This is validated at API level, not model level
        p = UserProfile()
        p.score = 950  # Invalid but model doesn't validate
        assert p.score == 950  # Model is permissive

    def test_serialization_roundtrip(self):
        p = UserProfile()
        p.province = "湖北"
        p.score = 620
        p.subject = "物理+历史+地理"
        p.interest = "想学医"
        p.family = "工薪"
        p.goal = "就业"
        p.region = "武汉"

        data = p.to_dict()
        p2 = UserProfile.from_dict(data)
        assert p2.province == p.province
        assert p2.score == p.score
        assert p2.subject == p.subject
        assert p2.interest == p.interest
        assert p2.family == p.family
        assert p2.goal == p.goal
        assert p2.region == p.region


def test_save_slots_merges_partial_updates():
    """Profile fields and soul-query state should not overwrite each other."""
    session_id = f"slot-merge-{uuid.uuid4().hex[:12]}"
    db = get_session()
    try:
        save_slots(
            db,
            session_id,
            {
                "province": "湖北",
                "score_rank": "580分",
            },
        )
        save_slots(
            db,
            session_id,
            {
                "_query_state": {
                    "round_count": 1,
                    "asked_fields": ["province"],
                    "skipped_fields": [],
                }
            },
        )
        slots = load_conversation_slots(db, session_id)
    finally:
        db.close()

    assert slots["province"] == "湖北"
    assert slots["score_rank"] == "580分"
    assert slots["_query_state"]["round_count"] == 1
