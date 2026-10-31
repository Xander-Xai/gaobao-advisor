"""Safety checks for destructive MySQL test URLs."""

from __future__ import annotations

import pytest

from tests.mysql_guard import assert_safe_test_url


def test_accepts_dedicated_test_database_name():
    assert_safe_test_url("mysql+pymysql://root:secret@127.0.0.1:3307/gaobao_test?charset=utf8mb4")


def test_rejects_non_test_database_name():
    with pytest.raises(RuntimeError, match="non-test database"):
        assert_safe_test_url("mysql+pymysql://root:secret@127.0.0.1:3307/gaobao")


def test_rejects_database_url_equal_to_production_url(monkeypatch):
    url = "mysql+pymysql://root:secret@127.0.0.1:3307/gaobao_test?charset=utf8mb4"
    monkeypatch.setenv("DATABASE_URL", url)
    with pytest.raises(RuntimeError, match="must not equal DATABASE_URL"):
        assert_safe_test_url(url)


def test_rejects_non_mysql_url():
    with pytest.raises(RuntimeError, match="must be a MySQL URL"):
        assert_safe_test_url("sqlite:///data/gaobao_test.db")
