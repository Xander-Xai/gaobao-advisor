"""Regression tests for CodeQL HTML-filter findings."""

from __future__ import annotations

from legacy.utils import sanitize_html
from server.middleware.security import sanitize_input


def test_legacy_sanitizer_removes_uppercase_and_spaced_script_tags():
    payload = "<p>ok</p><SCRIPT>alert(1)</SCRIPT ><style>body{}</style >"
    cleaned = sanitize_html(payload)
    assert "ok" in cleaned
    assert "alert(1)" not in cleaned
    assert "body{}" not in cleaned
    assert "script" not in cleaned.lower()


def test_sanitize_input_strips_tags_without_quadratic_scanning():
    assert sanitize_input("<b>hello</b>") == "hello"
    assert "<script>" not in sanitize_input("<script>alert(1)</script>")
    assert len(sanitize_input("<" * 20_000 + "b" + ">" * 20_000)) <= 3000
