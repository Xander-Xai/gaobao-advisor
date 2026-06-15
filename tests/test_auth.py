"""Tests for session HMAC token authentication."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.auth import create_session_token, verify_session_token


class TestSessionToken:
    def test_create_returns_string(self):
        token = create_session_token("session-123456")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_valid_token(self):
        token = create_session_token("session-123456")
        result = verify_session_token("session-123456", token)
        assert result is True

    def test_verify_wrong_session_id(self):
        token = create_session_token("session-123456")
        result = verify_session_token("session-999999", token)
        assert result is False

    def test_verify_tampered_token(self):
        token = create_session_token("session-123456")
        tampered = token[:-4] + "XXXX"
        result = verify_session_token("session-123456", tampered)
        assert result is False

    def test_verify_empty_token(self):
        result = verify_session_token("session-123456", "")
        assert result is False

    def test_verify_none_token(self):
        result = verify_session_token("session-123456", None)
        assert result is False
