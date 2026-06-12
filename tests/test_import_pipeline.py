"""Tests for enhanced import functions."""
import pytest
from unittest.mock import patch, MagicMock


def test_import_schools_fills_missing_city():
    """Existing school with empty city should get city from API."""
    from scrapers.baidu_gaokao import import_schools_to_db

    mock_school = MagicMock()
    mock_school.name = "测试大学"
    mock_school.province = "广东"
    mock_school.city = ""  # empty
    mock_school.ranking = None  # empty
    mock_school.description = None  # empty
    mock_school.school_type = "综合"

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = mock_school

    mock_item = {
        "college_name": "测试大学",
        "province": "广东",
        "city": "广州",
        "school_type": "理工",
        "rank": 50,
        "tag": ["211"],
        "tag_text": "211重点大学",
    }

    with patch("scrapers.baidu_gaokao.iter_schools", return_value=iter([mock_item])):
        stats = import_schools_to_db(mock_session, MagicMock(), max_schools=1, skip_existing=True)

    # Verify city was filled (was empty)
    assert mock_school.city == "广州", f"city should be filled from API, got {mock_school.city}"
    # Verify ranking was filled (was None)
    assert mock_school.ranking == 50, f"ranking should be filled from API, got {mock_school.ranking}"
    # Verify description was filled (was None)
    assert mock_school.description == "211重点大学", f"description should be filled from API, got {mock_school.description}"


def test_import_schools_does_not_overwrite_existing_city():
    """Existing school with non-empty city should keep its value."""
    from scrapers.baidu_gaokao import import_schools_to_db

    mock_school = MagicMock()
    mock_school.name = "测试大学"
    mock_school.province = "广东"
    mock_school.city = "深圳"  # already filled
    mock_school.ranking = 10  # already filled
    mock_school.description = "已有描述"  # already filled
    mock_school.school_type = "综合"

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = mock_school

    mock_item = {
        "college_name": "测试大学",
        "province": "广东",
        "city": "广州",
        "school_type": "理工",
        "rank": 50,
        "tag": ["211"],
        "tag_text": "211重点大学",
    }

    with patch("scrapers.baidu_gaokao.iter_schools", return_value=iter([mock_item])):
        stats = import_schools_to_db(mock_session, MagicMock(), max_schools=1, skip_existing=True)

    # City should NOT be overwritten
    assert mock_school.city == "深圳"
    assert mock_school.ranking == 10
    assert mock_school.description == "已有描述"
    # school_type IS synced from API (it is not a "fill only if empty" field)
    assert mock_school.school_type == "理工", f"school_type should sync from API, got {mock_school.school_type}"
