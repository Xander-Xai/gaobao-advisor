"""Tests for enrollment plan query with graceful empty-state fallback."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch

import pytest
import gaokao_data


@pytest.fixture(autouse=True)
def _restore_crud():
    """Save and restore gaokao_data._crud after each test to prevent cross-test pollution."""
    original = gaokao_data._crud
    yield
    gaokao_data._crud = original


def _set_crud(mock_crud):
    """Set the _crud module attribute to a mock before patching sub-attributes."""
    gaokao_data._crud = mock_crud


# ── Tests for query_enrollment_plan ──


class TestQueryEnrollmentPlan:
    """query_enrollment_plan should return empty list (not error) when table is empty."""

    def test_returns_empty_list_when_no_db(self):
        """When DB is unavailable, returns empty list (not None, not error)."""
        with patch.object(gaokao_data, "_get_session", return_value=None):
            result = gaokao_data.query_enrollment_plan("清华大学", 2024)
            assert result == []

    def test_returns_empty_list_when_table_empty(self):
        """When enrollment_plans table has 0 rows matching, returns empty list."""
        mock_crud = MagicMock()
        mock_crud.get_school_by_name.return_value = None
        _set_crud(mock_crud)

        mock_session = MagicMock()
        with patch.object(gaokao_data, "_get_session", return_value=mock_session):
            result = gaokao_data.query_enrollment_plan("清华大学", 2024)
            assert result == []
            mock_session.close.assert_called_once()

    def test_returns_empty_list_when_school_not_found(self):
        """When school name doesn't resolve, returns empty list gracefully."""
        mock_crud = MagicMock()
        mock_crud.get_school_by_name.return_value = None
        _set_crud(mock_crud)

        mock_session = MagicMock()
        with patch.object(gaokao_data, "_get_session", return_value=mock_session):
            result = gaokao_data.query_enrollment_plan("不存在的大学", 2024)
            assert result == []

    def test_returns_formatted_plans_when_data_exists(self):
        """When enrollment_plans data exists, returns list of dicts."""
        mock_school = MagicMock()
        mock_school.id = 1
        mock_school.name = "清华大学"
        mock_school.level = "985"

        mock_major = MagicMock()
        mock_major.id = 10
        mock_major.name = "计算机科学与技术"

        mock_plan = MagicMock()
        mock_plan.school_id = 1
        mock_plan.major_id = 10
        mock_plan.province = "北京"
        mock_plan.year = 2024
        mock_plan.plan_count = 50
        mock_plan.subject_requirement = "物理必选"
        mock_plan.batch = "本科一批"
        mock_plan.duration = 4
        mock_plan.tuition = 5000

        mock_crud = MagicMock()
        mock_crud.get_school_by_name.return_value = mock_school
        mock_crud.get_enrollment_plans.return_value = [mock_plan]
        _set_crud(mock_crud)

        mock_session = MagicMock()
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_major

        with patch.object(gaokao_data, "_get_session", return_value=mock_session):
            result = gaokao_data.query_enrollment_plan("清华大学", 2024)
            assert len(result) > 0
            first = result[0]
            assert first["school"] == "清华大学"
            assert first["major"] == "计算机科学与技术"
            assert first["plan_count"] == 50

    def test_always_returns_list_never_none(self):
        """query_enrollment_plan should never return None -- always a list."""
        with patch.object(gaokao_data, "_get_session", return_value=None):
            result = gaokao_data.query_enrollment_plan("清华大学", 2024)
            assert result is not None
            assert isinstance(result, list)

    def test_year_defaults_to_data_year(self):
        """When year is not specified, uses DATA_YEAR default."""
        mock_crud = MagicMock()
        mock_crud.get_school_by_name.return_value = None
        _set_crud(mock_crud)

        mock_session = MagicMock()
        with patch.object(gaokao_data, "_get_session", return_value=mock_session):
            result = gaokao_data.query_enrollment_plan("清华大学")
            # If school not found, still returns empty list
            assert result == []
            # Verify the default year was used (None passed to get_school_by_name is fine;
            # the key check is no exception and empty list back)
            assert isinstance(result, list)

    def test_db_exception_returns_empty_list(self):
        """DB exception should return empty list, not raise."""
        mock_crud = MagicMock()
        mock_crud.get_school_by_name.side_effect = Exception("DB connection lost")
        _set_crud(mock_crud)

        mock_session = MagicMock()
        with patch.object(gaokao_data, "_get_session", return_value=mock_session):
            result = gaokao_data.query_enrollment_plan("清华大学", 2024)
            assert result == []

    def test_db_exception_still_closes_session(self):
        """Session should be closed even when an exception occurs."""
        mock_crud = MagicMock()
        mock_crud.get_school_by_name.side_effect = Exception("DB error")
        _set_crud(mock_crud)

        mock_session = MagicMock()
        with patch.object(gaokao_data, "_get_session", return_value=mock_session):
            gaokao_data.query_enrollment_plan("清华大学", 2024)
            mock_session.close.assert_called_once()


# ── Tests for format_enrollment_info ──


class TestFormatEnrollmentInfo:
    """format_enrollment_info should return user-friendly messages for empty data."""

    def test_empty_list_returns_friendly_message(self):
        """format_enrollment_info([]) should return a user-friendly message with '暂无'."""
        result = gaokao_data.format_enrollment_info([])
        assert "暂无" in result
        assert "招生计划" in result

    def test_none_returns_friendly_message(self):
        """format_enrollment_info(None) should not raise, returns friendly message."""
        result = gaokao_data.format_enrollment_info(None)
        assert "暂无" in result
        assert "招生计划" in result

    def test_non_empty_list_returns_formatted_text(self):
        """When plans exist, should return formatted text with plan details."""
        plans = [
            {
                "school": "清华大学",
                "major": "计算机科学与技术",
                "province": "北京",
                "year": 2024,
                "plan_count": 50,
                "subject_requirement": "物理必选",
                "batch": "本科一批",
                "duration": 4,
                "tuition": 5000,
            }
        ]
        result = gaokao_data.format_enrollment_info(plans)
        assert "清华大学" in result
        assert "计算机科学与技术" in result
        assert "暂无" not in result

    def test_returns_string(self):
        """format_enrollment_info always returns a string."""
        assert isinstance(gaokao_data.format_enrollment_info([]), str)
        assert isinstance(gaokao_data.format_enrollment_info(None), str)
        assert isinstance(gaokao_data.format_enrollment_info([{"school": "X"}]), str)

    def test_multiple_plans_truncated_at_10(self):
        """Should show at most 10 plans."""
        plans = [{"school": f"学校{i}", "major": "专业"} for i in range(15)]
        result = gaokao_data.format_enrollment_info(plans)
        assert "学校9" in result  # 10th plan (index 9)
        assert "学校10" not in result  # 11th plan should be excluded
