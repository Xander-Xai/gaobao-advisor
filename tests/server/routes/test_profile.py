"""Tests for server/routes/profile.py — Profile endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from server.routes.profile import (
    ProfileUpdateRequest,
    _require_auth,
)


class TestRequireAuth:
    """Tests for _require_auth helper."""

    def test_valid_bearer_token(self):
        """Valid Bearer token should pass authentication."""
        with patch("server.routes.profile.verify_session_token", return_value=True):
            # Should not raise
            _require_auth("session123", "Bearer valid-token")

    def test_missing_authorization_header(self):
        """Missing Authorization header should raise 401."""
        with pytest.raises(HTTPException) as exc_info:
            _require_auth("session123", None)
        assert exc_info.value.status_code == 401
        assert "Missing session token" in exc_info.value.detail

    def test_invalid_bearer_prefix(self):
        """Authorization without Bearer prefix should raise 401."""
        with pytest.raises(HTTPException) as exc_info:
            _require_auth("session123", "Basic some-token")
        assert exc_info.value.status_code == 401

    def test_invalid_token(self):
        """Invalid token should raise 401."""
        with patch("server.routes.profile.verify_session_token", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                _require_auth("session123", "Bearer invalid-token")
            assert exc_info.value.status_code == 401
            assert "Invalid or expired" in exc_info.value.detail

    def test_token_strip_whitespace(self):
        """Token with extra whitespace should be stripped."""
        with patch("server.routes.profile.verify_session_token", return_value=True) as mock_verify:
            _require_auth("session123", "Bearer  valid-token  ")
            mock_verify.assert_called_once_with("session123", "valid-token")


class TestProfileUpdateRequest:
    """Tests for ProfileUpdateRequest model."""

    def test_valid_request(self):
        """Valid request should be accepted."""
        req = ProfileUpdateRequest(field="province", value="北京")
        assert req.field == "province"
        assert req.value == "北京"

    def test_field_too_long(self):
        """Field names longer than 32 chars should be rejected."""
        with pytest.raises(ValueError):
            ProfileUpdateRequest(field="a" * 33, value="test")

    def test_value_too_long(self):
        """Values longer than 200 chars should be rejected."""
        with pytest.raises(ValueError):
            ProfileUpdateRequest(field="province", value="x" * 201)

    def test_empty_field_rejected(self):
        """Empty field should be rejected."""
        with pytest.raises(ValueError):
            ProfileUpdateRequest(field="", value="test")

    def test_empty_value_rejected(self):
        """Empty value should be rejected."""
        with pytest.raises(ValueError):
            ProfileUpdateRequest(field="province", value="")


class TestGetProfile:
    """Tests for GET /api/v1/profile/{session_id}."""

    @pytest.mark.asyncio
    async def test_get_profile_success(self):
        """Valid request should return profile."""
        from server.routes.profile import get_profile

        mock_profile = MagicMock()
        mock_profile.to_dict.return_value = {"province": "北京", "score": 600}
        mock_profile.is_required_complete.return_value = False
        mock_profile.missing_required_fields.return_value = ["score", "subject"]

        with patch("server.routes.profile._require_auth"), \
             patch("server.routes.profile.load_profile", return_value=mock_profile):

            result = await get_profile("session123", "Bearer valid-token")

            assert result.session_id == "session123"
            assert result.profile["province"] == "北京"
            assert result.is_complete is False
            assert "score" in result.missing_fields

    @pytest.mark.asyncio
    async def test_get_profile_complete(self):
        """Complete profile should return is_complete=True."""
        from server.routes.profile import get_profile

        mock_profile = MagicMock()
        mock_profile.to_dict.return_value = {"province": "北京", "score": 600}
        mock_profile.is_required_complete.return_value = True
        mock_profile.missing_required_fields.return_value = []

        with patch("server.routes.profile._require_auth"), \
             patch("server.routes.profile.load_profile", return_value=mock_profile):

            result = await get_profile("session123", "Bearer valid-token")

            assert result.is_complete is True
            assert len(result.missing_fields) == 0


class TestUpdateProfileField:
    """Tests for PUT /api/v1/profile/{session_id}."""

    @pytest.mark.asyncio
    async def test_update_valid_string_field(self):
        """Updating a valid string field should succeed."""
        from server.routes.profile import update_profile_field

        mock_profile = MagicMock()
        mock_profile.to_dict.return_value = {"province": "上海"}
        mock_profile.is_required_complete.return_value = False
        mock_profile.missing_required_fields.return_value = ["score"]

        req = ProfileUpdateRequest(field="province", value="上海")

        with patch("server.routes.profile._require_auth"), \
             patch("server.routes.profile.load_profile", return_value=mock_profile), \
             patch("server.routes.profile.save_profile") as mock_save:

            result = await update_profile_field("session123", req, "Bearer valid-token")

            assert mock_profile.province == "上海"
            mock_save.assert_called_once()
            assert result.profile["province"] == "上海"

    @pytest.mark.asyncio
    async def test_update_score_valid(self):
        """Updating score with valid value should succeed."""
        from server.routes.profile import update_profile_field

        mock_profile = MagicMock()
        mock_profile.to_dict.return_value = {"score": 650}
        mock_profile.is_required_complete.return_value = False
        mock_profile.missing_required_fields.return_value = []

        req = ProfileUpdateRequest(field="score", value="650")

        with patch("server.routes.profile._require_auth"), \
             patch("server.routes.profile.load_profile", return_value=mock_profile), \
             patch("server.routes.profile.save_profile"):

            result = await update_profile_field("session123", req, "Bearer valid-token")

            assert mock_profile.score == 650

    @pytest.mark.asyncio
    async def test_update_score_out_of_range(self):
        """Score outside 100-750 range should be rejected."""
        from server.routes.profile import update_profile_field

        mock_profile = MagicMock()
        req = ProfileUpdateRequest(field="score", value="99")  # Too low

        with patch("server.routes.profile._require_auth"), \
             patch("server.routes.profile.load_profile", return_value=mock_profile):

            with pytest.raises(HTTPException) as exc_info:
                await update_profile_field("session123", req, "Bearer valid-token")

            assert exc_info.value.status_code == 400
            assert "100 and 750" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_update_score_non_numeric(self):
        """Non-numeric score should be rejected."""
        from server.routes.profile import update_profile_field

        mock_profile = MagicMock()
        req = ProfileUpdateRequest(field="score", value="abc")

        with patch("server.routes.profile._require_auth"), \
             patch("server.routes.profile.load_profile", return_value=mock_profile):

            with pytest.raises(HTTPException) as exc_info:
                await update_profile_field("session123", req, "Bearer valid-token")

            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_update_invalid_field(self):
        """Updating an invalid field should be rejected."""
        from server.routes.profile import update_profile_field

        mock_profile = MagicMock()
        req = ProfileUpdateRequest(field="invalid_field", value="test")

        with patch("server.routes.profile._require_auth"), \
             patch("server.routes.profile.load_profile", return_value=mock_profile):

            with pytest.raises(HTTPException) as exc_info:
                await update_profile_field("session123", req, "Bearer valid-token")

            assert exc_info.value.status_code == 400
            assert "Invalid field" in exc_info.value.detail


class TestGetNextQuestion:
    """Tests for GET /api/v1/profile/{session_id}/next-question."""

    @pytest.mark.asyncio
    async def test_get_next_question_success(self):
        """Should return next question."""
        from server.routes.profile import get_next_question

        mock_engine = MagicMock()
        mock_engine.get_next_question.return_value = "你的目标学校是哪一类？"
        mock_engine.is_query_complete.return_value = False

        mock_profile = MagicMock()
        mock_query_state = MagicMock()
        mock_query_state.round_count = 3

        with patch("server.routes.profile._require_auth"), \
             patch("server.routes.profile.get_soul_query_engine", return_value=mock_engine), \
             patch("server.routes.profile.load_profile", return_value=mock_profile), \
             patch("server.routes.profile._load_query_state", return_value=mock_query_state), \
             patch("server.routes.profile._save_query_state"):

            result = await get_next_question("session123", "Bearer valid-token")

            assert result.question == "你的目标学校是哪一类？"
            assert result.round_count == 3
            assert result.is_complete is False

    @pytest.mark.asyncio
    async def test_get_next_question_complete(self):
        """Should indicate completion when query is complete."""
        from server.routes.profile import get_next_question

        mock_engine = MagicMock()
        mock_engine.get_next_question.return_value = None
        mock_engine.is_query_complete.return_value = True

        mock_profile = MagicMock()
        mock_query_state = MagicMock()
        mock_query_state.round_count = 5

        with patch("server.routes.profile._require_auth"), \
             patch("server.routes.profile.get_soul_query_engine", return_value=mock_engine), \
             patch("server.routes.profile.load_profile", return_value=mock_profile), \
             patch("server.routes.profile._load_query_state", return_value=mock_query_state), \
             patch("server.routes.profile._save_query_state"):

            result = await get_next_question("session123", "Bearer valid-token")

            assert result.question is None
            assert result.is_complete is True


class TestSkipField:
    """Tests for POST /api/v1/profile/{session_id}/skip."""

    @pytest.mark.asyncio
    async def test_skip_field_success(self):
        """Skipping a field should succeed."""
        from server.routes.profile import skip_field, SkipFieldRequest

        mock_engine = MagicMock()
        mock_query_state = MagicMock()

        req = SkipFieldRequest(field="family")

        with patch("server.routes.profile._require_auth"), \
             patch("server.routes.profile.get_soul_query_engine", return_value=mock_engine), \
             patch("server.routes.profile._load_query_state", return_value=mock_query_state), \
             patch("server.routes.profile._save_query_state"):

            result = await skip_field("session123", req, "Bearer valid-token")

            assert result["status"] == "skipped"
            assert result["field"] == "family"
            mock_engine.handle_skip.assert_called_once_with(mock_query_state, "family")


class TestQueryStatePersistence:
    """Tests for query state loading and saving.

    Note: These tests focus on the public interface. The actual db layer
    behavior is tested via integration tests.
    """

    @pytest.mark.asyncio
    async def test_query_state_key_format(self):
        """Query state key should be correctly formatted."""
        from server.routes.profile import _query_state_key

        key = _query_state_key("session123")
        assert key == "query_state:session123"

    @pytest.mark.asyncio
    async def test_query_state_key_unique_per_session(self):
        """Different sessions should have different query state keys."""
        from server.routes.profile import _query_state_key

        key1 = _query_state_key("session1")
        key2 = _query_state_key("session2")
        assert key1 != key2