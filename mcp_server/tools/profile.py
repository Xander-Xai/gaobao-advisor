"""User profile MCP tools."""

from mcp.server.fastmcp import FastMCP

from mcp_server.client import get_client
from mcp_server.schemas import (
    GetProfileInput,
    ProfileOutput,
    UpdateProfileInput,
)


def register_profile_tools(mcp: FastMCP) -> None:
    """Register user profile tools with the MCP server."""

    @mcp.tool()
    async def gaobao_get_profile(input: GetProfileInput) -> ProfileOutput:  # noqa: N802
        """Retrieve a student's current profile and completeness status.

        Gets the stored profile information including province, score, subject,
        interests, and other fields. Also indicates which required fields are
        still missing.

        Args:
            input: Session ID to identify the student.

        Returns:
            ProfileOutput with profile data and completeness status.
        """
        client = get_client()

        data = await client.get(
            f"/api/v1/profile/{input.session_id}",
        )

        return ProfileOutput(
            session_id=data.get("session_id", input.session_id),
            profile=data.get("profile", {}),
            is_complete=data.get("is_complete", False),
            missing_fields=data.get("missing_fields", []),
        )

    @mcp.tool()
    async def gaobao_update_profile(input: UpdateProfileInput) -> ProfileOutput:  # noqa: N802
        """Update a specific field in the student's profile.

        Valid fields: province, score, subject, interest, region, family, goal.
        The score field must be an integer between 100 and 750.

        Args:
            input: Session ID, field name, and new value.

        Returns:
            Updated ProfileOutput with new completeness status.
        """
        client = get_client()

        data = await client.put(
            f"/api/v1/profile/{input.session_id}",
            json_data={
                "field": input.field,
                "value": input.value,
            },
        )

        return ProfileOutput(
            session_id=data.get("session_id", input.session_id),
            profile=data.get("profile", {}),
            is_complete=data.get("is_complete", False),
            missing_fields=data.get("missing_fields", []),
        )
