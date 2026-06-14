"""Tests for the AI-era risk assessment data module."""

from quality.ai_era_risk import get_major_risk, get_risk_summary


def test_exact_match_returns_risk():
    """Exact major name match should return risk data."""
    risk = get_major_risk("会计学")
    assert risk is not None
    assert risk["risk_zone"] == "🔴 高风险"
    assert "ai_impact" in risk
    assert "recommendation" in risk


def test_fuzzy_match_returns_risk():
    """Partial name match should return risk data."""
    risk = get_major_risk("新闻")
    assert risk is not None
    assert risk["risk_zone"] == "🔴 高风险"


def test_low_risk_major():
    """Low-risk major should return appropriate risk data."""
    risk = get_major_risk("电气工程及其自动化")
    assert risk is not None
    assert "🟢" in risk["risk_zone"] or "低风险" in risk["risk_zone"]


def test_unknown_major_returns_none():
    """Unknown major should return None."""
    risk = get_major_risk("火星殖民学")
    assert risk is None


def test_risk_summary_format():
    """Risk summary should be a formatted string."""
    summary = get_risk_summary("计算机科学与技术")
    assert summary is not None
    assert "风险" in summary or "建议" in summary


def test_empty_string_returns_none():
    """Empty string should return None, not match every major."""
    risk = get_major_risk("")
    assert risk is None


def test_none_returns_none():
    """None input should return None gracefully."""
    risk = get_major_risk(None)
    assert risk is None
