"""System-level MCP tools."""

from mcp.server.fastmcp import FastMCP

from mcp_server.client import get_client
from mcp_server.schemas import HealthCheckOutput


def register_system_tools(mcp: FastMCP) -> None:
    """Register system-level tools with the MCP server."""

    @mcp.tool()
    async def gaobao_health_check() -> HealthCheckOutput:  # noqa: N802
        """Check the health status of the gaobao-advisor service.

        Verifies that the API server is running and the database connection
        is active. Use this to diagnose connectivity issues.

        Returns:
            HealthCheckOutput with status, version, and database state.
        """
        client = get_client()

        data = await client.get("/api/v1/health")

        return HealthCheckOutput(
            status=data.get("status", "unknown"),
            version=data.get("version", "unknown"),
            database=data.get("database", "unknown"),
        )
