"""LLM reasoning node -- calls the LLM to generate a conversational reply."""
from __future__ import annotations

import os
import sys
import threading
from typing import Any, Generator

from openai import OpenAI

# Ensure project root is on path for config import
# This is needed when llm_node.py is imported directly (e.g. by chat.py's
# streaming path) rather than through the main server entry point which
# already adds the project root to sys.path.
_PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config.loader import load_llm_config


_client: OpenAI | None = None
_client_lock = threading.Lock()
_config: dict | None = None


def _get_config() -> dict:
    """Load LLM config from YAML + env vars (cached)."""
    global _config
    if _config is None:
        _config = load_llm_config()
    return _config


def _get_llm_client() -> OpenAI:
    global _client
    cfg = _get_config()
    if _client is None:
        with _client_lock:
            if _client is None:
                api_key = cfg["api_key"]
                if not api_key:
                    raise RuntimeError("LLM_API_KEY must be set (via config/llm_providers.yaml or env)")
                _client = OpenAI(
                    api_key=api_key,
                    base_url=cfg["base_url"],
                )
    return _client


_SYSTEM_PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "system_prompt.md"
)


def _load_system_prompt() -> str:
    try:
        with open(_SYSTEM_PROMPT_PATH, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "你是一个资深高考志愿规划师。"


_FALLBACK_REPLY = (
    "抱歉，我现在暂时无法给出完整分析。"
    "请稍后再试，或者告诉我你的省份和分数，我帮你做个初步判断。"
)


def _build_user_message(state: dict[str, Any]) -> str:
    """Build the user message with full context from state."""
    reasoning = state.get("reasoning", "")
    emotion = state.get("emotion_state", "🟢")
    heuristics = state.get("decision_heuristics", [])

    user_parts = [f"以下是分析上下文：\n{reasoning}"]

    if emotion and emotion != "🟢":
        user_parts.append(f"⚠️ 用户情绪状态：{emotion}（请先共情再给建议）")

    if heuristics:
        user_parts.append(f"决策启发：{'; '.join(heuristics[:5])}")

    user_parts.append("请基于以上信息，用你的人设和表达方式，给出回复。")
    return "\n\n".join(user_parts)


def llm_node(state: dict[str, Any]) -> dict[str, Any]:
    """Call the LLM to generate a conversational reply (non-streaming)."""
    user_message = _build_user_message(state)
    trace = list(state.get("trace", []))
    cfg = _get_config()

    try:
        client = _get_llm_client()
        system_prompt = _load_system_prompt()

        response = client.chat.completions.create(
            model=cfg["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=cfg.get("temperature", 0.7),
            max_tokens=cfg.get("max_tokens") or 2000,
        )
        content = response.choices[0].message.content
        reply = (content or "").strip()
        if not reply:
            reply = _FALLBACK_REPLY
    except Exception as exc:
        reply = _FALLBACK_REPLY
        trace.append({"node": "llm_reason", "event": "llm_error", "error": str(exc)[:200]})

    trace.append({"node": "llm_reason", "event": "llm_reply_generated"})
    return {"reply": reply, "trace": trace}


def llm_node_stream(state: dict[str, Any]) -> Generator[str, None, None]:
    """Stream LLM tokens one by one. Yields token strings."""
    user_message = _build_user_message(state)
    cfg = _get_config()

    try:
        client = _get_llm_client()
        system_prompt = _load_system_prompt()

        stream = client.chat.completions.create(
            model=cfg["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=cfg.get("temperature", 0.7),
            max_tokens=cfg.get("max_tokens") or 2000,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception:
        yield _FALLBACK_REPLY
