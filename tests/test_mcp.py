"""Tests for MCP server — validation of schemas, client, and tool registration.

Note: These tests validate code correctness without requiring
the gaobao-advisor API to be running.
"""

import pytest
from pydantic import ValidationError

from mcp_server.client import GaobaoAPIError, GaobaoClient, get_client, reset_client
from mcp_server.schemas import (
    ChatInput,
    GetProfileInput,
    GetQuotesInput,
    GetSchoolDetailInput,
    HealthCheckOutput,
    QueryPlansInput,
    QueryScoresInput,
    SearchKnowledgeInput,
    SearchSchoolsInput,
    SearchSchoolsOutput,
    UpdateProfileInput,
)


class TestSchoolSchemas:
    """Test school-related schema validation."""

    def test_search_schools_input_minimal(self):
        s = SearchSchoolsInput(limit=10)
        assert s.school_name is None
        assert s.province is None
        assert s.level is None
        assert s.limit == 10

    def test_search_schools_input_full(self):
        s = SearchSchoolsInput(school_name="浙江", province="浙江", level="985", limit=50)
        assert s.school_name == "浙江"
        assert s.province == "浙江"
        assert s.level == "985"
        assert s.limit == 50

    def test_search_schools_limit_range(self):
        """Limit must be between 1 and 200."""
        SearchSchoolsInput(limit=1)
        SearchSchoolsInput(limit=200)

    def test_get_school_detail_input(self):
        s = GetSchoolDetailInput(school_name="北京大学")
        assert s.school_name == "北京大学"

    def test_search_schools_output(self):
        s = SearchSchoolsOutput(count=0, items=[], next_cursor=None, has_more=False)
        assert s.count == 0
        assert s.items == []


class TestScoreSchemas:
    """Test score query schema validation."""

    def test_query_scores_input(self):
        s = QueryScoresInput(school_name="北京大学", province="北京")
        assert s.school_name == "北京大学"
        assert s.province == "北京"
        assert s.year is None
        assert s.major is None
        assert s.limit == 10

    def test_query_scores_input_with_year_major(self):
        s = QueryScoresInput(school_name="清华", province="浙江", year=2024, major="计算机")
        assert s.year == 2024
        assert s.major == "计算机"

    def test_query_plans_input(self):
        s = QueryPlansInput(school_name="北京大学")
        assert s.school_name == "北京大学"
        assert s.province is None
        assert s.year is None
        assert s.limit == 10


class TestKnowledgeSchemas:
    """Test knowledge base schema validation."""

    def test_search_knowledge_input(self):
        s = SearchKnowledgeInput(query="计算机专业就业前景")
        assert s.query == "计算机专业就业前景"
        assert s.top_k == 5
        assert s.groups is None

    def test_search_knowledge_input_with_groups(self):
        s = SearchKnowledgeInput(query="清华大学", groups=["院校", "专业"], top_k=10)
        assert s.groups == ["院校", "专业"]
        assert s.top_k == 10

    def test_get_quotes_input(self):
        s = GetQuotesInput(major="计算机", top_k=10)
        assert s.major == "计算机"
        assert s.top_k == 10


class TestProfileSchemas:
    """Test profile schema validation."""

    def test_get_profile_input(self):
        s = GetProfileInput(session_id="test-session-123")
        assert s.session_id == "test-session-123"

    def test_get_profile_input_min_length(self):
        """Session ID must be at least 4 characters."""
        s = GetProfileInput(session_id="abc1")
        assert s.session_id == "abc1"

    def test_update_profile_input_valid_fields(self):
        for field in ["province", "score", "subject", "interest", "region", "family", "goal"]:
            s = UpdateProfileInput(session_id="test-123", field=field, value="test")
            assert s.field == field

    def test_update_profile_input_invalid_field(self):
        with pytest.raises(ValidationError):
            UpdateProfileInput(session_id="test-123", field="invalid_field", value="test")


class TestChatSchemas:
    """Test chat schema validation."""

    def test_chat_input(self):
        s = ChatInput(session_id="test-123", message="清华大学计算机专业怎么样")
        assert s.session_id == "test-123"
        assert s.scene == "gaokao"

    def test_chat_input_with_slots(self):
        s = ChatInput(
            session_id="test-abc",
            message="有什么推荐的学校",
            scene="postgraduate",
            slots={"score": 650, "province": "浙江"},
        )
        assert s.slots == {"score": 650, "province": "浙江"}


class TestSystemSchemas:
    """Test system schema validation."""

    def test_health_check_output(self):
        s = HealthCheckOutput(status="ok", version="3.1.0", database="connected")
        assert s.status == "ok"


class TestGaobaoClient:
    """Test client initialization."""

    def test_client_creation(self):
        reset_client()
        client = GaobaoClient(base_url="http://localhost:8000")
        assert client.base_url == "http://localhost:8000"
        assert client.api_key == ""

    def test_client_creation_with_api_key(self):
        client = GaobaoClient(base_url="http://test:8000", api_key="test-key-123")
        assert client.base_url == "http://test:8000"
        assert client.api_key == "test-key-123"

    def test_client_singleton(self):
        reset_client()
        c1 = get_client()
        c2 = get_client()
        assert c1 is c2


class TestGaobaoAPIError:
    """Test custom API error."""

    def test_error_creation(self):
        err = GaobaoAPIError("Something went wrong", status_code=500)
        assert str(err) == "Something went wrong"
        assert err.status_code == 500

    def test_error_default_status(self):
        err = GaobaoAPIError("Connection failed")
        assert err.status_code == 0


class TestToolRegistration:
    """Test that all tool registration functions exist and are callable."""

    def test_tool_imports(self):

        from mcp_server.tools import (
            register_knowledge_tools,
            register_profile_tools,
            register_school_tools,
            register_score_tools,
            register_system_tools,
        )

        # All functions should exist
        assert callable(register_school_tools)
        assert callable(register_score_tools)
        assert callable(register_knowledge_tools)
        assert callable(register_profile_tools)
        assert callable(register_system_tools)

    def test_server_creation(self):
        from mcp_server.server import mcp as server_instance

        assert server_instance.name == "gaobao-advisor"
        assert "高考志愿" in server_instance.instructions
        assert "院校搜索" in server_instance.instructions
