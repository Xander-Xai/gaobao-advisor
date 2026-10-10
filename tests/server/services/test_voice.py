"""Tests for the voice service — prompts, styles, and rendering."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.services.voice import (
    SCENE_VOICE_STYLES,
    VOICE_RENDER_SYSTEM_PROMPT,
    VoiceService,
    get_voice_service,
)


class TestVoiceRenderPrompt:
    """VOICE_RENDER_SYSTEM_PROMPT should guide the LLM to produce spoken-style output."""

    def test_prompt_is_non_empty_string(self):
        assert isinstance(VOICE_RENDER_SYSTEM_PROMPT, str)
        assert len(VOICE_RENDER_SYSTEM_PROMPT) > 50

    def test_prompt_mentions_key_constraints(self):
        prompt = VOICE_RENDER_SYSTEM_PROMPT
        has_length_constraint = "200" in prompt or "200字" in prompt
        has_spoken = "口语" in prompt
        assert has_length_constraint or has_spoken, "Prompt should have constraints or spoken-style requirement"

    def test_prompt_mentions_zhangxuefeng(self):
        assert "张雪峰" in VOICE_RENDER_SYSTEM_PROMPT, "Should reference the advising methodology"


class TestSceneVoiceStyles:
    """SCENE_VOICE_STYLES should define tone for each supported scene."""

    def test_contains_required_scenes(self):
        assert "gaokao" in SCENE_VOICE_STYLES
        assert "kaoyan" in SCENE_VOICE_STYLES
        assert "career" in SCENE_VOICE_STYLES

    def test_all_styles_are_non_empty(self):
        for scene, style in SCENE_VOICE_STYLES.items():
            assert isinstance(style, str), f"Style for {scene} should be string"
            assert len(style) > 10, f"Style for {scene} should be descriptive"

    def test_gaokao_style_is_encouraging(self):
        assert "温暖" in SCENE_VOICE_STYLES["gaokao"] or "鼓励" in SCENE_VOICE_STYLES["gaokao"]

    def test_kaoyan_style_is_analytical(self):
        assert "理性" in SCENE_VOICE_STYLES["kaoyan"] or "分析" in SCENE_VOICE_STYLES["kaoyan"]

    def test_career_style_is_direct(self):
        assert "务实" in SCENE_VOICE_STYLES["career"] or "直接" in SCENE_VOICE_STYLES["career"]


class TestVoiceService:
    """VoiceService lifecycle and fallback behavior."""

    def test_init_without_env(self, monkeypatch):
        """With no DASHSCOPE_CHAT_API_KEY, service should be unavailable."""
        monkeypatch.delenv("DASHSCOPE_CHAT_API_KEY", raising=False)
        service = VoiceService()
        assert service.is_available() is False
        assert service.chat_api_key == ""

    def test_init_with_env(self, monkeypatch):
        """With DASHSCOPE_CHAT_API_KEY set, service should be available."""
        monkeypatch.setenv("DASHSCOPE_CHAT_API_KEY", "test-key-123")
        service = VoiceService()
        assert service.is_available() is True
        assert service.chat_api_key == "test-key-123"

    def test_is_available_false_when_no_key(self):
        """is_available returns False when api_key is empty."""
        service = VoiceService()
        service.chat_api_key = ""
        assert service.is_available() is False

    def test_is_available_true_when_key_present(self):
        """is_available returns True when api_key is non-empty."""
        service = VoiceService()
        service.chat_api_key = "some-key"
        assert service.is_available() is True

    @pytest.mark.asyncio
    async def test_render_voice_reply_fallback_on_exception(self):
        """When no API key is set, render_voice_reply returns original text as fallback."""
        service = VoiceService()
        assert service.chat_api_key == ""
        original = "This is the original planning conclusion."
        result = await service.render_voice_reply(original)
        assert result == original

    @pytest.mark.asyncio
    async def test_render_voice_reply_fallback_with_env(self, monkeypatch):
        """render_voice_reply falls back to original text even when env is set."""
        monkeypatch.setenv("DASHSCOPE_CHAT_API_KEY", "test-key")
        service = VoiceService()
        assert service.chat_api_key == "test-key"
        original = "Some planning text."

        with patch("openai.AsyncOpenAI", side_effect=RuntimeError("network")):
            result = await service.render_voice_reply(original)

        assert result == original

    @pytest.mark.asyncio
    async def test_render_voice_reply_success(self, monkeypatch):
        """render_voice_reply returns the LLM response on success."""
        monkeypatch.setenv("DASHSCOPE_CHAT_API_KEY", "test-key")
        service = VoiceService()

        # Mock the OpenAI client at module level
        mock_message = MagicMock()
        mock_message.content = " Voiced output. "
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_openai_instance = MagicMock()
        mock_openai_instance.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai_instance.close = AsyncMock()

        with patch("openai.AsyncOpenAI", return_value=mock_openai_instance):
            result = await service.render_voice_reply("Some text.")

        assert result == "Voiced output."
        mock_openai_instance.chat.completions.create.assert_called_once()


class TestGetVoiceService:
    """get_voice_service singleton behavior."""

    def test_returns_voice_service_instance(self):
        instance = get_voice_service()
        assert isinstance(instance, VoiceService)

    def test_singleton_same_instance(self):
        svc1 = get_voice_service()
        svc2 = get_voice_service()
        assert svc1 is svc2
