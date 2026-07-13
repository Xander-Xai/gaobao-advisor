"""Tool registration helpers."""

from mcp_server.tools.knowledge import register_knowledge_tools
from mcp_server.tools.profile import register_profile_tools
from mcp_server.tools.schools import register_school_tools
from mcp_server.tools.scores import register_score_tools
from mcp_server.tools.system import register_system_tools

__all__ = [
    "register_knowledge_tools",
    "register_profile_tools",
    "register_school_tools",
    "register_score_tools",
    "register_system_tools",
]
