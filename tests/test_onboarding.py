"""
3-step onboarding flow tests.
Covers: OnboardingState dataclass, province mapping, to_slots, step progression.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from onboarding import (
    OnboardingState,
    PROVINCES,
    PROVINCE_MODES,
    SUBJECT_TYPES,
    INTERESTS,
)


# ── OnboardingState defaults ──


class TestOnboardingStateDefaults:
    def test_initial_step_is_1(self):
        state = OnboardingState()
        assert state.step == 1

    def test_initial_values_are_none(self):
        state = OnboardingState()
        assert state.province is None
        assert state.score is None
        assert state.subject is None
        assert state.interest is None

    def test_is_complete_false_when_incomplete(self):
        state = OnboardingState()
        assert state.is_complete() is False


# ── Province data ──


class TestProvinceData:
    def test_thirtyone_provinces(self):
        assert len(PROVINCES) == 31

    def test_all_provinces_have_mode(self):
        for prov in PROVINCES:
            assert prov in PROVINCE_MODES, f"{prov} missing from PROVINCE_MODES"

    def test_33_provinces_correct(self):
        expected_33 = {"浙江", "上海", "北京", "天津", "山东", "海南"}
        for prov in expected_33:
            assert PROVINCE_MODES[prov] == "3+3", f"{prov} should be 3+3"

    def test_312_provinces_correct(self):
        expected_312 = {
            "河北", "辽宁", "江苏", "福建", "湖北", "湖南",
            "广东", "重庆", "安徽", "江西", "贵州", "广西",
            "甘肃", "黑龙江", "吉林",
        }
        for prov in expected_312:
            assert PROVINCE_MODES[prov] == "3+1+2", f"{prov} should be 3+1+2"


# ── Subject and interest data ──


class TestSubjectAndInterestData:
    def test_subject_types_not_empty(self):
        assert len(SUBJECT_TYPES) > 0

    def test_interests_not_empty(self):
        assert len(INTERESTS) > 0

    def test_subject_types_are_strings(self):
        for subj in SUBJECT_TYPES:
            assert isinstance(subj, str)

    def test_interests_are_strings(self):
        for interest in INTERESTS:
            assert isinstance(interest, str)


# ── Step progression methods ──


class TestStepProgression:
    def test_set_province_advances_to_step_2(self):
        state = OnboardingState()
        state.set_province("山东")
        assert state.province == "山东"
        assert state.step == 2

    def test_set_score_advances_to_step_3(self):
        state = OnboardingState()
        state.set_province("山东")
        state.set_score(580)
        assert state.score == 580
        assert state.step == 3

    def test_set_subject_and_interest_completes(self):
        state = OnboardingState()
        state.set_province("山东")
        state.set_score(580)
        state.set_subject("物化生")
        state.set_interest("计算机")
        assert state.is_complete() is True
        assert state.step == 3

    def test_incomplete_state(self):
        state = OnboardingState()
        state.set_province("山东")
        assert state.is_complete() is False


# ── Score validation ──


class TestScoreValidation:
    def test_valid_score(self):
        state = OnboardingState()
        state.set_province("山东")
        state.set_score(580)
        assert state.score == 580

    def test_zero_score(self):
        state = OnboardingState()
        state.set_province("山东")
        state.set_score(0)
        assert state.score == 0

    def test_max_score(self):
        state = OnboardingState()
        state.set_province("山东")
        state.set_score(900)
        assert state.score == 900


# ── to_slots conversion ──


class TestToSlots:
    def test_to_slots_returns_dict(self):
        state = OnboardingState(
            step=3,
            province="山东",
            score=580,
            subject="物化生",
            interest="计算机",
        )
        slots = state.to_slots()
        assert isinstance(slots, dict)

    def test_to_slots_has_required_keys(self):
        state = OnboardingState(
            step=3,
            province="山东",
            score=580,
            subject="物化生",
            interest="计算机",
        )
        slots = state.to_slots()
        assert "province" in slots
        assert "score_rank" in slots
        assert "subject" in slots
        assert "interest" in slots

    def test_to_slots_province_filled(self):
        state = OnboardingState(
            step=3,
            province="山东",
            score=580,
            subject="物化生",
            interest="计算机",
        )
        slots = state.to_slots()
        assert slots["province"]["filled"] is True
        assert slots["province"]["value"] == "山东"

    def test_to_slots_score_rank_value(self):
        state = OnboardingState(
            step=3,
            province="山东",
            score=580,
            subject="物化生",
            interest="计算机",
        )
        slots = state.to_slots()
        assert slots["score_rank"]["filled"] is True
        assert slots["score_rank"]["value"] == 580

    def test_to_slots_subject_filled(self):
        state = OnboardingState(
            step=3,
            province="山东",
            score=580,
            subject="物化生",
            interest="计算机",
        )
        slots = state.to_slots()
        assert slots["subject"]["filled"] is True
        assert slots["subject"]["value"] == "物化生"

    def test_to_slots_interest_filled(self):
        state = OnboardingState(
            step=3,
            province="山东",
            score=580,
            subject="物化生",
            interest="计算机",
        )
        slots = state.to_slots()
        assert slots["interest"]["filled"] is True
        assert slots["interest"]["value"] == "计算机"

    def test_to_slots_partial_state(self):
        state = OnboardingState(step=2, province="山东", score=580)
        slots = state.to_slots()
        assert slots["province"]["filled"] is True
        assert slots["score_rank"]["filled"] is True
        assert slots["subject"]["filled"] is False
        assert slots["interest"]["filled"] is False

    def test_to_slots_empty_state(self):
        state = OnboardingState()
        slots = state.to_slots()
        for key in ("province", "score_rank", "subject", "interest"):
            assert slots[key]["filled"] is False


# ── should_skip logic ──


class TestShouldSkip:
    def test_should_skip_when_no_messages_no_slots(self):
        """New user with no messages and no filled slots -> should NOT skip (show onboarding)."""
        state = OnboardingState()
        assert state.should_skip(has_user_messages=False, has_filled_slots=False) is False

    def test_should_skip_when_messages_exist(self):
        """User who already chatted -> skip onboarding."""
        state = OnboardingState()
        assert state.should_skip(has_user_messages=True, has_filled_slots=False) is True

    def test_should_skip_when_slots_filled(self):
        """Returning user with filled slots -> skip onboarding."""
        state = OnboardingState()
        assert state.should_skip(has_user_messages=True, has_filled_slots=True) is True

    def test_should_show_when_user_messaging(self):
        """User has messages but no slots filled -> skip (already chatting)."""
        state = OnboardingState()
        assert state.should_skip(has_user_messages=True, has_filled_slots=False) is True

    def test_should_not_skip_when_slots_only(self):
        """Slots filled but no messages (restored state) -> skip."""
        state = OnboardingState()
        assert state.should_skip(has_user_messages=False, has_filled_slots=True) is True
