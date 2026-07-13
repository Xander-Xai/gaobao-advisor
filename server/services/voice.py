"""Voice interaction service — ASR → LangGraph → Voice Rendering → TTS.

Adapted from EduAgent backend/app/modules/voice/service.py.
"""

import asyncio
import os

from config.loader import load_voice_config

VOICE_RENDER_SYSTEM_PROMPT = (
    "你是教育规划电话模式助手。\n"
    "你会收到一段已经完成推理的规划结论，请把它改写成适合电话里直接说出来的中文回复。\n"
    "语气必须更像张雪峰方法论驱动的顾问：直接、短句、先结论后展开、带一点推进感。\n"
    "不要使用 markdown 格式。不要列出要点。用口语化的方式串联信息。\n"
    "控制回复在 200 字以内。"
)

SCENE_VOICE_STYLES = {
    "gaokao": "温暖鼓励型：对考生和家长表达理解和支持，用积极的语言引导",
    "kaoyan": "理性分析型：客观分析利弊，用数据和逻辑支撑建议",
    "career": "务实直接型：直击核心，用实际案例和数据说话",
}

VOICE_RENDER_TIMEOUT_SECONDS = 10


class VoiceService:
    """Handles voice rendering (text → oral speech)."""

    def __init__(self) -> None:
        cfg = load_voice_config()
        self.chat_api_key = cfg["api_key"]
        self.chat_model = cfg["model"]
        self._base_url = os.getenv(
            "GAOBAO__VOICE__BASE_URL",
            os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        )
        from config.loader import load_tuning

        _voice_cfg = load_tuning().get("voice", {})
        self._temperature = float(_voice_cfg.get("temperature", 0.7))
        self._max_tokens = int(_voice_cfg.get("max_tokens", 500))

    async def render_voice_reply(self, text: str, scene: str = "gaokao") -> str:
        """Use LLM to rewrite structured reply into oral-style speech."""
        if not self.chat_api_key:
            return text

        try:
            from openai import AsyncOpenAI

            style = SCENE_VOICE_STYLES.get(scene, "")
            client = AsyncOpenAI(
                api_key=self.chat_api_key,
                base_url=self._base_url,
                timeout=VOICE_RENDER_TIMEOUT_SECONDS,
                max_retries=0,
            )

            try:
                response = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=self.chat_model,
                        messages=[
                            {
                                "role": "system",
                                "content": VOICE_RENDER_SYSTEM_PROMPT + f"\n语气风格：{style}",
                            },
                            {
                                "role": "user",
                                "content": f"请将以下规划结论改写为电话中直接说出来的口语：\n\n{text}",
                            },
                        ],
                        temperature=self._temperature,
                        max_tokens=self._max_tokens,
                    ),
                    timeout=VOICE_RENDER_TIMEOUT_SECONDS,
                )
            finally:
                await client.close()

            content = response.choices[0].message.content
            return (content or "").strip() or text
        except Exception:
            return text  # Fallback: return original text if rendering fails

    def is_available(self) -> bool:
        """Check if voice service is configured."""
        return bool(self.chat_api_key)


_voice_service: VoiceService | None = None


def get_voice_service() -> VoiceService:
    global _voice_service
    if _voice_service is None:
        _voice_service = VoiceService()
    return _voice_service
