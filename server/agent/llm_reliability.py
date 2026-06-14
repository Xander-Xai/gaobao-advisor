"""LLM reliability utilities — retry, context trimming, token estimation.

Migrated and adapted from zhangxuefeng-agent's AgentCore patterns:
- _retry_api_call  (backend/agent/core.py:31-51)
- _trim_messages  (backend/agent/core.py:54-69)
- _estimate_tokens (backend/agent/langchain_agent.py:37-39)

Design:
- All functions are stateless and thread-safe.
- `retry_api_call` accepts a coroutine factory (not a coroutine) so each
  retry attempt gets a fresh API call, avoiding "can't reuse already consumed
  coroutine" errors.
- `trim_messages` preserves system prompt + recent N rounds of conversation.
- `estimate_tokens` uses a conservative heuristic for Chinese text (~1.5 chars/token).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────
MAX_RETRIES = 2
RETRYABLE_STATUS_CODES = {429, 500, 502, 503}
MAX_HISTORY_ROUNDS = 20  # Keep system + recent 20 rounds (40 messages)
SUMMARY_TOKEN_BUDGET = 2000  # Trigger LLM summary if older messages exceed this

T = TypeVar("T")


# ── Retry logic ────────────────────────────────────────────────────


async def retry_api_call(
    coro_factory: Callable[[], Coroutine[Any, Any, T]],
    max_retries: int = MAX_RETRIES,
    base_delay: float = 1.0,
    logger_name: str = __name__,
) -> T:
    """Call *coro_factory* and retry on retryable status codes with
    exponential backoff.

    Args:
        coro_factory: Factory that returns a new coroutine each call.
            Must be a callable, not a coroutine — each retry needs
            a fresh API call object.
        max_retries: Maximum number of retries (0 = no retry).
        base_delay: Base delay in seconds (doubles each retry).
        logger_name: Logger name for warnings.

    Returns:
        The coroutine result.

    Raises:
        The last exception if max retries exceeded or a non-retryable error.
    """
    _log = logging.getLogger(logger_name)
    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            return await coro_factory()
        except Exception as e:
            status = _extract_status(e)
            if status in RETRYABLE_STATUS_CODES and attempt < max_retries:
                delay = base_delay * (2**attempt)
                _log.warning(
                    "API call failed (status=%s), retry %d/%d in %.1fs...",
                    status,
                    attempt + 1,
                    max_retries,
                    delay,
                )
                await asyncio.sleep(delay)
                last_exc = e
            else:
                raise

    # Should not reach here, but keep the type checker happy
    raise last_exc  # type: ignore[misc]


def _extract_status(exc: Exception) -> int | None:
    """Try to extract an HTTP status code from an exception."""
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    return status if isinstance(status, int) else None


# ── Context trimming ──────────────────────────────────────────────


def trim_messages(
    messages: list[dict],
    max_rounds: int = MAX_HISTORY_ROUNDS,
) -> list[dict]:
    """Trim message history to keep system prompt + recent *max_rounds*.

    One round = 1 user message + 1 assistant message (or tool chain).
    Older messages beyond the limit are discarded.

    Args:
        messages: Full message list (first element assumed to be system).
        max_rounds: Number of recent rounds to keep.

    Returns:
        Trimmed message list (always includes the system prompt).
    """
    if not messages:
        return messages

    # Find system prompt(s) — keep all system messages at the front
    system_messages: list[dict] = []
    non_system_start = 0
    for i, msg in enumerate(messages):
        if msg.get("role") == "system":
            system_messages.append(msg)
        else:
            non_system_start = i
            break

    non_system = messages[non_system_start:]
    max_to_keep = max_rounds * 2  # user + assistant per round

    if len(non_system) <= max_to_keep:
        return messages

    dropped = len(non_system) - max_to_keep
    kept = non_system[-max_to_keep:]

    logger.info(
        "Context trimmed: dropped %d old messages, keeping %d recent (system=%d)",
        dropped,
        len(kept),
        len(system_messages),
    )

    return system_messages + kept


# ── Token estimation ──────────────────────────────────────────────


def estimate_tokens(text: str | None) -> int:
    """Rough token count for Chinese text (~1.5 chars per token).

    English text is closer to 4 chars/token; this is intentionally
    conservative (overestimates slightly) to avoid exceeding context limits.
    """
    if not text:
        return 0
    return max(1, len(text) // 2)


def estimate_messages_tokens(messages: list[dict]) -> int:
    """Estimate total tokens in a message list."""
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        total += 4  # Overhead per message (role markers, etc.)
    return total


# ── Build user message context ─────────────────────────────────────


def build_llm_context(state: dict[str, Any]) -> str:
    """Build the user message context string from graph state.

    This replaces the inline logic previously in llm_node._build_user_message,
    making it reusable for both sync and async paths.
    """
    reasoning = state.get("reasoning", "")
    emotion = state.get("emotion_state", "🟢")
    heuristics = state.get("decision_heuristics", [])

    parts = [f"以下是分析上下文：\n{reasoning}"]

    if emotion and emotion != "🟢":
        parts.append(f"⚠️ 用户情绪状态：{emotion}（请先共情再给建议）")

    if heuristics:
        parts.append(f"决策启发：{'; '.join(heuristics[:5])}")

    parts.append("请基于以上信息，用你的人设和表达方式，给出回复。")

    return "\n\n".join(parts)
