"""Tests for server/agent/llm_reliability.py — retry, trim, token estimation."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from server.agent.llm_reliability import (
    RETRYABLE_STATUS_CODES,
    build_llm_context,
    estimate_messages_tokens,
    estimate_tokens,
    retry_api_call,
    trim_messages,
)

# ── Fixtures ────────────────────────────────────────────────────────


class _RetryableError(Exception):
    """Simulates a retryable API error with status_code."""

    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}")


class _NonRetryableError(Exception):
    """Simulates a non-retryable error."""

    def __init__(self, msg: str = "bad request"):
        self.status_code = 400
        super().__init__(msg)


class _NoStatusError(Exception):
    """Simulates an error without status_code attr."""

    pass


# ── Test: estimate_tokens ───────────────────────────────────────────


class TestEstimateTokens:
    def test_empty_and_none(self):
        assert estimate_tokens("") == 0
        assert estimate_tokens(None) == 0

    def test_short_text(self):
        assert estimate_tokens("a") == 1
        assert estimate_tokens("hi") == 1

    def test_chinese_text(self):
        # ~1.5 chars per token → 10 chars → 5 tokens
        text = "高考志愿填报建议"  # 8 chars
        result = estimate_tokens(text)
        assert result == 4  # 8 // 2

    def test_long_text(self):
        text = "我是" * 500  # 1000 chars
        assert estimate_tokens(text) == 500

    def test_mixed_text(self):
        text = "hello世界"  # 7 chars → 7//2 = 3
        assert estimate_tokens(text) == 3

    def test_min_return(self):
        assert estimate_tokens("a") == 1


# ── Test: estimate_messages_tokens ──────────────────────────────────


class TestEstimateMessagesTokens:
    def test_empty_list(self):
        assert estimate_messages_tokens([]) == 0

    def test_single_message(self):
        msgs = [{"role": "user", "content": "四字"}]
        # content: 2 chars // 2 = 1 token + 4 overhead
        assert estimate_messages_tokens(msgs) == 5

    def test_multiple_messages(self):
        msgs = [
            {"role": "system", "content": "你是一个助手"},
            {"role": "user", "content": "高考多少分"},
        ]
        result = estimate_messages_tokens(msgs)
        # "你是一个助手": 6 chars → 3 tokens
        # "高考多少分": 5 chars → 2 tokens
        # + 4 overhead each = 3 + 4 + 2 + 4 = 13
        assert result == 13

    def test_messages_with_other_keys(self):
        msgs = [
            {"role": "system", "content": "你好"},
            {"role": "user", "content": "在吗", "name": "张三"},
        ]
        # "你好" 2 chars → 1 token, +4 = 5
        # "在吗" 2 chars → 1 token, +4 = 5
        assert estimate_messages_tokens(msgs) == 10


# ── Test: trim_messages ─────────────────────────────────────────────


class TestTrimMessages:
    def test_empty(self):
        assert trim_messages([]) == []

    def test_system_only(self):
        msgs = [{"role": "system", "content": "你是一个助手"}]
        assert trim_messages(msgs) == msgs

    def test_within_limit(self):
        msgs = [
            {"role": "system", "content": "你是一个助手"},
            {"role": "user", "content": "1"},
            {"role": "assistant", "content": "2"},
        ]
        # 3 messages < 1*2 + 1 = 3 → unchanged
        assert trim_messages(msgs, max_rounds=1) == msgs

    def test_exceeds_limit(self):
        msgs = [
            {"role": "system", "content": "你是一个助手"},
            {"role": "user", "content": "a"},
            {"role": "assistant", "content": "b"},
            {"role": "user", "content": "c"},
            {"role": "assistant", "content": "d"},
        ]
        trimmed = trim_messages(msgs, max_rounds=1)
        # Keep system + last 2 messages
        assert len(trimmed) == 3
        assert trimmed[0] == msgs[0]
        assert trimmed[1:] == msgs[-2:]

    def test_preserves_multiple_system_messages(self):
        msg_sys1 = {"role": "system", "content": "s1"}
        msg_sys2 = {"role": "system", "content": "s2"}
        msgs = [
            msg_sys1,
            msg_sys2,
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "u2"},
            {"role": "assistant", "content": "a2"},
            {"role": "user", "content": "u3"},
        ]
        trimmed = trim_messages(msgs, max_rounds=1)
        assert len(trimmed) == 4  # 2 system + 2 recent
        assert trimmed[0] == msg_sys1
        assert trimmed[1] == msg_sys2
        assert trimmed[2:] == msgs[-2:]

    def test_exact_limit_no_trim(self):
        msgs = [
            {"role": "system", "content": "s"},
        ]
        for i in range(10):
            msgs.append({"role": "user", "content": str(i)})
            msgs.append({"role": "assistant", "content": str(i)})
        # 21 msgs total, limit = 10 rounds = 20 non-system → exactly at boundary
        assert trim_messages(msgs, max_rounds=10) == msgs

    def test_just_over_limit(self):
        msgs = [{"role": "system", "content": "s"}]
        for i in range(11):
            msgs.append({"role": "user", "content": str(i)})
            msgs.append({"role": "assistant", "content": str(i)})
        # 23 msgs total, limit = 10 rounds = 20 non-system
        trimmed = trim_messages(msgs, max_rounds=10)
        assert len(trimmed) == 21  # 1 system + 20 recent
        assert trimmed[0] == msgs[0]
        assert trimmed[1:] == msgs[-20:]


# ── Test: retry_api_call ────────────────────────────────────────────


class TestRetryApiCall:
    @pytest.mark.asyncio
    async def test_success_first_attempt(self):
        factory = AsyncMock(return_value="ok")
        result = await retry_api_call(factory, max_retries=2)
        assert result == "ok"
        factory.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_then_success(self):
        call_count = 0

        async def _factory():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise _RetryableError(429)
            return "success"

        result = await retry_api_call(_factory, max_retries=3, base_delay=0.01)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_non_retryable_error_propagates(self):
        factory = AsyncMock(side_effect=_NonRetryableError("bad input"))
        with pytest.raises(_NonRetryableError, match="bad input"):
            await retry_api_call(factory, max_retries=2)

    @pytest.mark.asyncio
    async def test_exhaust_retries_raises(self):
        factory = AsyncMock(side_effect=_RetryableError(503))
        with pytest.raises(_RetryableError):
            await retry_api_call(factory, max_retries=1, base_delay=0.01)
        assert factory.call_count == 2  # original + 1 retry

    @pytest.mark.asyncio
    async def test_zero_retries_no_retry(self):
        factory = AsyncMock(side_effect=_RetryableError(502))
        with pytest.raises(_RetryableError):
            await retry_api_call(factory, max_retries=0)
        factory.assert_called_once()

    @pytest.mark.asyncio
    async def test_delay_increases_exponentially(self):
        call_count = 0
        delays = []

        async def _factory():
            nonlocal call_count
            call_count += 1
            raise _RetryableError(429)

        async def _tracking_sleep(delay):
            delays.append(delay)

        with patch("asyncio.sleep", _tracking_sleep):
            with pytest.raises(_RetryableError):
                await retry_api_call(_factory, max_retries=2, base_delay=0.5)

        # delays should be: 0.5, 1.0 (base * 2^0, base * 2^1)
        assert len(delays) == 2
        assert abs(delays[0] - 0.5) < 0.01
        assert abs(delays[1] - 1.0) < 0.01

    @pytest.mark.asyncio
    async def test_non_http_error_passthrough(self):
        """Errors without status_code should propagate immediately."""
        factory = AsyncMock(side_effect=_NoStatusError("connection reset"))
        with pytest.raises(_NoStatusError):
            await retry_api_call(factory, max_retries=2)

    @pytest.mark.asyncio
    async def test_mixed_codes_retryable_first_then_non_retryable(self):
        call_count = 0

        async def _factory():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise _RetryableError(500)
            raise _NonRetryableError("validation error")

        with pytest.raises(_NonRetryableError, match="validation error"):
            await retry_api_call(_factory, max_retries=2, base_delay=0.01)
        assert call_count == 2


# ── Test: build_llm_context ─────────────────────────────────────────


class TestBuildLlmContext:
    def test_basic_context(self):
        state = {
            "reasoning": "用户580分，河南理科",
            "emotion_state": "🟢",
            "decision_heuristics": ["分数优先", "城市优先"],
        }
        ctx = build_llm_context(state)
        assert "580分" in ctx
        assert "河南" in ctx
        assert "分数优先" in ctx
        assert "情绪" not in ctx  # neutral emotion, no warning

    def test_emotion_warning_included(self):
        state = {
            "reasoning": "用户很焦虑",
            "emotion_state": "🔴",
            "decision_heuristics": [],
        }
        ctx = build_llm_context(state)
        assert "🔴" in ctx
        assert "先共情" in ctx

    def test_missing_fields(self):
        state: dict = {}
        ctx = build_llm_context(state)
        assert ctx is not None
        assert "分析上下文" in ctx

    def test_heuristics_truncated(self):
        state = {
            "reasoning": "分析完成",
            "emotion_state": "🟢",
            "decision_heuristics": [f"启发式{i}" for i in range(10)],
        }
        ctx = build_llm_context(state)
        # Should only include up to 5
        assert "启发式4" in ctx
        assert "启发式5" not in ctx


# ── Test: retryable status codes ────────────────────────────────────


class TestRetryableCodes:
    def test_standard_codes_present(self):
        assert 429 in RETRYABLE_STATUS_CODES
        assert 500 in RETRYABLE_STATUS_CODES
        assert 502 in RETRYABLE_STATUS_CODES
        assert 503 in RETRYABLE_STATUS_CODES
