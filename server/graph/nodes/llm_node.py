"""LLM reasoning node -- calls the LLM to generate a conversational reply."""
from __future__ import annotations

import os
import threading
from typing import Any

from openai import OpenAI


_client: OpenAI | None = None
_client_lock = threading.Lock()


def _get_llm_client() -> OpenAI:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
                if not api_key:
                    raise RuntimeError("LLM_API_KEY or OPENAI_API_KEY must be set")
                _client = OpenAI(
                    api_key=api_key,
                    base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
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


def llm_node(state: dict[str, Any]) -> dict[str, Any]:
    """Call the LLM to generate a conversational reply from the assembled context.

    Reads system_prompt.md as the system message, builds a user message
    from the reasoning context and quality signals, and calls the LLM.
    On failure, returns a graceful fallback reply.
    """
    reasoning = state.get("reasoning", "")
    emotion = state.get("emotion_state", "🟢")
    model = state.get("cognitive_model", "default")
    heuristics = state.get("decision_heuristics", [])

    # Build the user message with full context
    user_parts = [f"以下是分析上下文：\n{reasoning}"]

    if emotion and emotion != "🟢":
        user_parts.append(f"⚠️ 用户情绪状态：{emotion}（请先共情再给建议）")

    if heuristics:
        user_parts.append(f"决策启发：{'; '.join(heuristics[:5])}")

    user_parts.append("请基于以上信息，用你的人设和表达方式，给出回复。")
    user_message = "\n\n".join(user_parts)

    trace = list(state.get("trace", []))

    try:
        client = _get_llm_client()
        system_prompt = _load_system_prompt()

        response = client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "deepseek-chat"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.7,
            max_tokens=2000,
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
