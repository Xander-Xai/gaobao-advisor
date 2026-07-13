"""School-related MCP tools."""

from mcp.server.fastmcp import FastMCP

from mcp_server.client import GaobaoAPIError, get_client
from mcp_server.schemas import (
    GetSchoolDetailInput,
    SchoolDetail,
    SearchSchoolsInput,
    SearchSchoolsOutput,
)


def register_school_tools(mcp: FastMCP) -> None:
    """Register school-related tools with the MCP server."""

    @mcp.tool()
    async def gaobao_search_schools(input: SearchSchoolsInput) -> SearchSchoolsOutput:  # noqa: N802
        """Search for universities and colleges in the gaokao database.

        Use this tool to find schools matching criteria like name, province,
        or tier (985/211/Double First-Class). Returns paginated results.

        Args:
            input: Search parameters including optional name, province, level filters.

        Returns:
            SearchSchoolsOutput with matching schools and pagination info.
        """
        client = get_client()

        # Build query params
        params: dict = {"limit": input.limit}
        if input.school_name:
            params["school_name"] = input.school_name
        if input.province:
            params["province"] = input.province
        if input.level:
            params["level"] = input.level

        data = await client.get("/api/v1/data/schools", params=params)

        # Handle both paginated and direct results
        if "results" in data:
            # Direct search results (school_name query)
            items = data.get("results", [])
            return SearchSchoolsOutput(
                count=len(items),
                items=items,
                next_cursor=None,
                has_more=False,
            )

        # Paginated results
        items = data.get("items", [])
        return SearchSchoolsOutput(
            count=len(items),
            items=items,
            next_cursor=data.get("next_cursor"),
            has_more=data.get("has_more", False),
        )

    @mcp.tool()
    async def gaobao_get_school_detail(input: GetSchoolDetailInput) -> SchoolDetail:  # noqa: N802
        """Get detailed information about a specific university.

        Retrieves comprehensive details including location, tier, type,
        and available majors for a given school name.

        Args:
            input: School name to look up.

        Returns:
            SchoolDetail with full school information.
        """
        client = get_client()

        # First search for the school
        search_data = await client.get(
            "/api/v1/data/schools",
            params={"school_name": input.school_name, "limit": 1},
        )

        results = search_data.get("results", []) if "results" in search_data else search_data.get("items", [])
        if not results:
            raise GaobaoAPIError(f"School not found: {input.school_name}", status_code=404)

        school = results[0]
        return SchoolDetail(
            name=school.get("name", input.school_name),
            province=school.get("province"),
            level=school.get("level"),
            type=school.get("type"),
            address=school.get("address"),
            website=school.get("website"),
            description=school.get("description"),
            majors=school.get("majors", []),
        )
