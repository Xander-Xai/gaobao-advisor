"""Gaobao Advisor MCP Server — Main entry point.

Exposes gaobao-advisor API capabilities through the Model Context Protocol,
enabling LLM agents to query university data, admission scores, enrollment
plans, knowledge base content, and user profiles.

Usage:
    python -m mcp.server          # Run as module
    python mcp/server.py          # Run directly

Environment:
    GAOBAO_API_BASE_URL  - API base URL (default: http://localhost:8000)
    GAOBAO_API_KEY       - Optional API key for authentication
    GAOBAO_TIMEOUT       - Request timeout in seconds (default: 30)
"""

import logging
import sys

from mcp.server.fastmcp import FastMCP

from mcp_server.tools import (
    register_knowledge_tools,
    register_profile_tools,
    register_school_tools,
    register_score_tools,
    register_system_tools,
)

# ── Logging ───────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("gaobao-mcp")

# ── Server Initialization ─────────────────────────────────

mcp = FastMCP(
    "gaobao-advisor",
    instructions=(
        "高考志愿 AI 顾问 MCP 服务器。\n"
        "提供以下能力：\n"
        "• 院校搜索与详情查询\n"
        "• 历年录取分数线查询\n"
        "• 招生计划查询\n"
        "• RAG 知识库语义检索\n"
        "• 专家金句获取\n"
        "• 考生画像管理\n"
        "\n"
        "所有工具以 `gaobao_` 为前缀命名。"
    ),
)

# ── Register Tools ────────────────────────────────────────

register_school_tools(mcp)
register_score_tools(mcp)
register_knowledge_tools(mcp)
register_profile_tools(mcp)
register_system_tools(mcp)

logger.info("All gaobao-advisor MCP tools registered")
logger.info(
    "MCP server ready — tools: gaobao_search_schools, gaobao_get_school_detail, gaobao_query_scores, gaobao_query_plans, gaobao_search_knowledge, gaobao_get_quotes, gaobao_get_profile, gaobao_update_profile, gaobao_health_check"
)

# ── Entry Point ───────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Starting gaobao-advisor MCP server...")
    mcp.run()
