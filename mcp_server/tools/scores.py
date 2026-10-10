"""Score and plan query MCP tools."""

from mcp.server.fastmcp import FastMCP

from mcp_server.client import get_client
from mcp_server.schemas import (
    PlanRecord,
    QueryPlansInput,
    QueryPlansOutput,
    QueryScoresInput,
    QueryScoresOutput,
    ScoreRecord,
)


def register_score_tools(mcp: FastMCP) -> None:
    """Register score and plan query tools with the MCP server."""

    @mcp.tool()
    async def gaobao_query_scores(input: QueryScoresInput) -> QueryScoresOutput:  # noqa: N802
        """Query historical admission scores for a university.

        Retrieves past years' admission score data including minimum, average,
        and maximum scores, as well as minimum rank positions. Useful for
        estimating admission probability based on historical trends.

        Args:
            input: Query parameters with school name, province, optional year/major.

        Returns:
            QueryScoresOutput with score records.
        """
        client = get_client()

        params: dict = {
            "school_name": input.school_name,
            "province": input.province,
            "limit": input.limit,
        }
        if input.year:
            params["year"] = input.year
        if input.major:
            params["major"] = input.major

        data = await client.get("/api/v1/data/scores", params=params)

        items = []
        for item in data.get("items", []):
            items.append(
                ScoreRecord(
                    school_name=item.get("school_name", input.school_name),
                    province=item.get("province", input.province),
                    year=item.get("year", 0),
                    batch=item.get("batch"),
                    subject_type=item.get("subject_type"),
                    min_score=item.get("min_score"),
                    avg_score=item.get("avg_score"),
                    max_score=item.get("max_score"),
                    min_rank=item.get("min_rank"),
                    major=item.get("major"),
                )
            )

        return QueryScoresOutput(
            count=len(items),
            items=items,
            has_more=data.get("has_more", False),
        )

    @mcp.tool()
    async def gaobao_query_plans(input: QueryPlansInput) -> QueryPlansOutput:  # noqa: N802
        """Query enrollment plans for a university.

        Retrieves the number of planned admissions, subject requirements,
        batch information, duration, and tuition fees for a given school.

        Args:
            input: Query parameters with school name, optional province/year.

        Returns:
            QueryPlansOutput with enrollment plan records.
        """
        client = get_client()

        params: dict = {
            "school_name": input.school_name,
            "limit": input.limit,
        }
        if input.province:
            params["province"] = input.province
        if input.year:
            params["year"] = input.year

        data = await client.get("/api/v1/data/plans", params=params)

        items = []
        for item in data.get("items", []):
            items.append(
                PlanRecord(
                    school_name=item.get("school_name", input.school_name),
                    province=item.get("province", ""),
                    year=item.get("year", 0),
                    plan_count=item.get("plan_count"),
                    subject_requirement=item.get("subject_requirement"),
                    batch=item.get("batch"),
                    duration=item.get("duration"),
                    tuition=item.get("tuition"),
                    major=item.get("major"),
                )
            )

        return QueryPlansOutput(
            count=len(items),
            items=items,
            has_more=data.get("has_more", False),
        )
