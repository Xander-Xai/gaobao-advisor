"""Tests for server/soul_query.py — soul query engine."""

from __future__ import annotations

import pytest

from server.soul_query import (
    MAX_QUERY_ROUNDS,
    OPTIONAL_QUESTIONS,
    REQUIRED_QUESTIONS,
    SKIP_DEFAULTS,
    QueryState,
    SoulQueryEngine,
)
from server.user_profile import UserProfile


@pytest.fixture
def engine():
    return SoulQueryEngine()


@pytest.fixture
def empty_profile():
    return UserProfile()


@pytest.fixture
def full_profile():
    p = UserProfile()
    p.province = "山东"
    p.score = 580
    p.subject = "理科"
    p.interest = "想学计算机"
    return p


class TestSoulQueryEngine:
    def test_empty_profile_returns_province_question(self, engine, empty_profile):
        state = QueryState()
        question = engine.get_next_question(empty_profile, state)
        assert question is not None
        assert "省" in question
        assert "province" in state.asked_fields
        assert state.round_count == 1

    def test_province_filled_returns_score_question(self, engine):
        profile = UserProfile()
        profile.province = "江苏"
        state = QueryState()
        question = engine.get_next_question(profile, state)
        assert question is not None
        assert "分" in question or "分数" in question
        assert "score" in state.asked_fields

    def test_all_required_complete_asks_optional(self, engine, full_profile):
        """When required is complete, the engine asks optional fields."""
        state = QueryState()
        question = engine.get_next_question(full_profile, state)
        # Required complete → first optional (region) is asked
        assert question is not None
        assert "城市" in question or "地区" in question

    def test_optional_cycle_through_all_optionals(self, engine, full_profile):
        """Engine asks all optional fields one by one."""
        state = QueryState()
        q1 = engine.get_next_question(full_profile, state)
        q2 = engine.get_next_question(full_profile, state)
        q3 = engine.get_next_question(full_profile, state)
        assert q1 is not None
        assert q2 is not None
        assert q3 is not None
        # After all optionals, should return None
        q4 = engine.get_next_question(full_profile, state)
        assert q4 is None

    def test_max_rounds_stops_questioning(self, engine, empty_profile):
        state = QueryState(round_count=MAX_QUERY_ROUNDS)
        question = engine.get_next_question(empty_profile, state)
        assert question is None

    def test_skipped_field_is_remembered(self, engine, full_profile):
        state = QueryState()
        engine.handle_skip(state, "region")
        assert "region" in state.skipped_fields

    def test_question_variants_cycle(self, engine, empty_profile):
        """Same field asked multiple times should cycle through variants."""
        field = "province"
        questions = REQUIRED_QUESTIONS[field]
        assert len(questions) >= 2

        for i in range(len(questions)):
            q = engine._pick_question(field, i)
            assert q == questions[i % len(questions)]

    def test_is_query_complete_true(self, engine, full_profile):
        assert engine.is_query_complete(full_profile) is True

    def test_is_query_complete_false(self, engine, empty_profile):
        assert engine.is_query_complete(empty_profile) is False

    def test_skip_defaults_return_correct_values(self, engine):
        assert engine.get_skip_default("region") == "不限"
        assert engine.get_skip_default("family") == "参考"
        assert engine.get_skip_default("goal") == "未确定"
        assert engine.get_skip_default("nonexistent") is None

    def test_apply_skip_defaults(self, engine, full_profile):
        full_profile.region = None
        full_profile.goal = None
        state = QueryState(
            asked_fields=["region", "goal"],
            skipped_fields=["region", "goal"],
        )
        engine.apply_skip_defaults(full_profile, state)
        assert full_profile.region == "不限"
        assert full_profile.goal == "未确定"

    def test_question_order_is_consistent(self, engine, empty_profile):
        """Required fields should be asked in a consistent order."""
        state = QueryState()
        q1 = engine.get_next_question(empty_profile, state)
        q2 = engine.get_next_question(empty_profile, state)
        q3 = engine.get_next_question(empty_profile, state)
        q4 = engine.get_next_question(empty_profile, state)

        assert q1 is not None
        assert q2 is not None
        assert q3 is not None
        assert q4 is not None

        # All should be different fields
        fields_asked = state.asked_fields[:4]
        assert len(set(fields_asked)) == 4


class TestQueryState:
    def test_default_initial_state(self):
        state = QueryState()
        assert state.round_count == 0
        assert state.asked_fields == []
        assert state.skipped_fields == []

    def test_can_track_asked_fields(self):
        state = QueryState()
        state.asked_fields.append("province")
        assert "province" in state.asked_fields

    def test_can_increment_round(self):
        state = QueryState()
        state.round_count += 1
        assert state.round_count == 1


class TestRequiredQuestions:
    def test_all_required_fields_have_questions(self):
        assert "province" in REQUIRED_QUESTIONS
        assert "score" in REQUIRED_QUESTIONS
        assert "subject" in REQUIRED_QUESTIONS
        assert "interest" in REQUIRED_QUESTIONS

    def test_all_required_have_at_least_two_variants(self):
        for field, questions in REQUIRED_QUESTIONS.items():
            assert len(questions) >= 2, f"{field} has only {len(questions)} variant(s)"

    def test_questions_contain_relevant_keywords(self):
        assert "省" in REQUIRED_QUESTIONS["province"][0]
        assert "分" in REQUIRED_QUESTIONS["score"][0]
        assert any(kw in REQUIRED_QUESTIONS["subject"][0] for kw in ["文科", "理科", "选科"])


class TestOptionalQuestions:
    def test_optional_questions_have_entries(self):
        assert OPTIONAL_QUESTIONS
        assert "region" in OPTIONAL_QUESTIONS
        assert "family" in OPTIONAL_QUESTIONS
        assert "goal" in OPTIONAL_QUESTIONS

    def test_skip_defaults_exist_for_all_optionals(self):
        for field in OPTIONAL_QUESTIONS:
            assert field in SKIP_DEFAULTS, f"{field} has no skip default"
