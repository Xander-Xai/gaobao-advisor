"""Regression tests for the canonical score/rank and profile slot contract."""

from server.graph.nodes.check import profile_check_node
from server.graph.nodes.extract import _parse_score_rank, slot_extract_node
from server.user_profile import UserProfile


def test_parse_score_rank_combined_value():
    assert _parse_score_rank("600分 / 位次25000") == (600, 25000)


def test_slot_extract_adds_canonical_score():
    result = slot_extract_node(
        {
            "input_text": "河北考生600分物理类想学计算机",
            "slots": {},
            "trace": [],
        }
    )
    slots = result["slots"]
    assert slots["score"] == 600
    assert "score_rank" in slots


def test_profile_accepts_flat_persisted_slots():
    profile = UserProfile.from_slots(
        {
            "province": "河北",
            "score_rank": "600分",
            "score": 600,
            "subject": "物理",
            "interest": "计算机",
        }
    )
    assert profile.province == "河北"
    assert profile.score == 600
    assert profile.subject == "物理"
    assert profile.interest == "计算机"
    assert profile.is_required_complete()


def test_profile_keeps_legacy_nested_slot_compatibility():
    profile = UserProfile.from_slots(
        {
            "province": {"value": "河北", "filled": True},
            "score_rank": {"value": "600分", "filled": True},
            "subject": {"value": "物理", "filled": True},
            "interest": {"value": "计算机", "filled": True},
        }
    )
    assert profile.score == 600
    assert profile.is_required_complete()


def test_profile_check_accepts_canonical_score_without_score_rank():
    result = profile_check_node(
        {
            "scene": "gaokao",
            "slots": {
                "province": "河北",
                "score": 600,
                "subject": "物理",
                "interest": "计算机",
            },
            "trace": [],
        }
    )
    assert "score_rank" not in result["missing_fields"]
