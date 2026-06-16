"""Tests for server/services/voice.py — VoiceService and get_voice_service."""

from unittest.mock import MagicMock, patch

import pytest

from server.services.voice import (
    SCENE_VOICE_STYLES,
    VOICE_RENDER_SYSTEM_PROMPT,
    VoiceService,
    get_voice_service,
)


class TestVoiceService:
    """Unit tests for VoiceService."""

    def test_init_reads_env(self, monkeypatch):
        """VoiceService reads DASHSCOPE_CHAT_API_KEY and DASHSCOPE_CHAT_MODEL from env."""
        monkeypatch.setenv("DASHSCOPE_CHAT_API_KEY", "test-key-123")
        monkeypatch.setenv("DASHSCOPE_CHAT_MODEL", "test-model")
        svc = VoiceService()
        assert svc.chat_api_key == "test-key-123"
        assert svc.chat_model == "test-model"

    def test_init_defaults(self, monkeypatch):
        """VoiceService uses sensible defaults when env vars are absent."""
        monkeypatch.delenv("DASHSCOPE_CHAT_API_KEY", raising=False)
        monkeypatch.delenv("DASHSCOPE_CHAT_MODEL", raising=False)
        svc = VoiceService()
        assert svc.chat_api_key == ""
        assert svc.chat_model == "qwen-plus"

    def test_is_available_true(self, monkeypatch):
        """is_available returns True when API key is configured."""
        monkeypatch.setenv("DASHSCOPE_CHAT_API_KEY", "sk-test")
        svc = VoiceService()
        assert svc.is_available() is True

    def test_is_available_false(self, monkeypatch):
        """is_available returns False when API key is missing."""
        monkeypatch.delenv("DASHSCOPE_CHAT_API_KEY", raising=False)
        svc = VoiceService()
        assert svc.is_available() is False

    @pytest.mark.asyncio
    async def test_render_voice_reply_success(self, monkeypatch):
        """render_voice_reply returns LLM-rewritten text on success."""
        monkeypatch.setenv("DASHSCOPE_CHAT_API_KEY", "sk-test")
        svc = VoiceService()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "  这是口语化后的回复  "

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            result = await svc.render_voice_reply("原始规划结论", scene="gaokao")

        assert result == "这是口语化后的回复"
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "qwen-plus"
        assert call_kwargs["temperature"] == 0.7
        assert call_kwargs["max_tokens"] == 500
        messages = call_kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert VOICE_RENDER_SYSTEM_PROMPT in messages[0]["content"]
        assert SCENE_VOICE_STYLES["gaokao"] in messages[0]["content"]
        assert messages[1]["content"] == "请将以下规划结论改写为电话中直接说出来的口语：\n\n原始规划结论"

    @pytest.mark.asyncio
    async def test_render_voice_reply_fallback_on_error(self, monkeypatch):
        """render_voice_reply returns original text when LLM call fails."""
        monkeypatch.setenv("DASHSCOPE_CHAT_API_KEY", "sk-test")
        svc = VoiceService()

        with patch("openai.OpenAI", side_effect=RuntimeError("network")):
            result = await svc.render_voice_reply("原始文本", scene="career")

        assert result == "原始文本"

    @pytest.mark.asyncio
    async def test_render_voice_reply_scene_styles(self, monkeypatch):
        """render_voice_reply injects correct scene style into system prompt."""
        monkeypatch.setenv("DASHSCOPE_CHAT_API_KEY", "sk-test")
        svc = VoiceService()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "ok"

        for scene in SCENE_VOICE_STYLES:
            with patch("openai.OpenAI") as mock_openai:
                mock_client = MagicMock()
                mock_client.chat.completions.create.return_value = mock_response
                mock_openai.return_value = mock_client

                await svc.render_voice_reply("test", scene=scene)

                call_kwargs = mock_client.chat.completions.create.call_args.kwargs
                system_content = call_kwargs["messages"][0]["content"]
                assert SCENE_VOICE_STYLES[scene] in system_content

    @pytest.mark.asyncio
    async def test_render_voice_reply_unknown_scene(self, monkeypatch):
        """render_voice_reply handles unknown scene gracefully (empty style)."""
        monkeypatch.setenv("DASHSCOPE_CHAT_API_KEY", "sk-test")
        svc = VoiceService()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "ok"

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            await svc.render_voice_reply("test", scene="unknown")

            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            system_content = call_kwargs["messages"][0]["content"]
            assert "语气风格：" in system_content


class TestGetVoiceService:
    """Tests for get_voice_service singleton."""

    def test_singleton(self, monkeypatch):
        """get_voice_service returns the same instance on repeated calls."""
        monkeypatch.setenv("DASHSCOPE_CHAT_API_KEY", "sk-test")
        # Reset module-level singleton
        import server.services.voice as voice_mod

        voice_mod._voice_service = None
        s1 = get_voice_service()
        s2 = get_voice_service()
        assert s1 is s2
        assert isinstance(s1, VoiceService)

    def test_singleton_no_env(self, monkeypatch):
        """get_voice_service works even without env vars."""
        monkeypatch.delenv("DASHSCOPE_CHAT_API_KEY", raising=False)
        import server.services.voice as voice_mod

        voice_mod._voice_service = None
        svc = get_voice_service()
        assert isinstance(svc, VoiceService)
        assert svc.is_available() is False
