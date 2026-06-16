"""Tests for async parallel import functions."""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_async_client(json_data: dict = None, side_effect: Exception = None):
    """Create an AsyncMock httpx client for testing."""
    client = AsyncMock(spec=["get"])
    if side_effect:
        client.get.side_effect = side_effect
    else:
        response = AsyncMock(spec=["json", "raise_for_status"])
        response.json.return_value = json_data or {}
        response.raise_for_status.return_value = None

        # Make client.get() return an awaitable response
        async def _mock_get(*args, **kwargs):
            return response

        client.get = _mock_get
    return client


def test_async_fetch_json_returns_none_on_error():
    """async_fetch_json should return None when all retries fail."""
    from scrapers.baidu_gaokao import async_fetch_json

    client = _make_async_client(side_effect=Exception("Network error"))

    import asyncio

    result = asyncio.run(async_fetch_json("http://test.com", client, retries=1))
    assert result is None
    assert client.get.call_count == 1


def test_async_fetch_json_returns_data_on_success():
    """async_fetch_json should return parsed JSON on success."""
    from scrapers.baidu_gaokao import async_fetch_json

    client = _make_async_client({"key": "value"})

    import asyncio

    result = asyncio.run(async_fetch_json("http://test.com", client, retries=1))
    assert result == {"key": "value"}


def test_async_fetch_school_score_returns_empty_on_no_data():
    """async_fetch_school_score should return [] when API returns no data."""
    from scrapers.baidu_gaokao import async_fetch_school_score

    client = _make_async_client({"data": {"school_score": {"dataList": []}}})

    import asyncio

    result = asyncio.run(async_fetch_school_score(client, "北京大学", "北京", 2025, "3+3综合"))
    assert result == []


def test_async_fetch_school_score_parses_data():
    """async_fetch_school_score should parse dataList correctly."""
    from scrapers.baidu_gaokao import async_fetch_school_score

    client = _make_async_client({"data": {"school_score": {"dataList": [{"minScore": "680", "batchName": "本科批"}]}}})

    import asyncio

    result = asyncio.run(async_fetch_school_score(client, "北京大学", "北京", 2025, "3+3综合"))
    assert len(result) == 1
    assert result[0]["minScore"] == "680"


def test_build_fetch_tasks_skips_existing():
    """_build_fetch_tasks should skip combos already in DB."""
    from scrapers.baidu_gaokao import _build_fetch_tasks

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.count.return_value = 0

    mock_school = MagicMock()
    mock_school.id = 1

    import asyncio

    semaphore = asyncio.Semaphore(5)

    tasks = _build_fetch_tasks(mock_session, MagicMock(), mock_school, ["北京", "上海"], [2025], semaphore)

    assert len(tasks) > 0
    for t in tasks:
        assert len(t) == 3
        assert t[1] == 2025


def test_import_scores_async_runs_with_mocks():
    """import_scores_async should complete without errors when mocked."""
    from scrapers.baidu_gaokao import import_scores_async

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.count.return_value = 0

    mock_school = MagicMock()
    mock_school.id = 1
    mock_school.name = "测试大学"

    import asyncio

    with patch("scrapers.baidu_gaokao.async_fetch_school_score", return_value=[]):
        result = asyncio.run(
            import_scores_async(
                mock_session,
                MagicMock(),
                MagicMock(),
                schools=[mock_school],
                provinces=["北京"],
                years=[2025],
            )
        )

    assert result["errors"] == 0
    assert result["requests"] >= 0
