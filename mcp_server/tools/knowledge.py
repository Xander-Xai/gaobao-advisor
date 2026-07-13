"""Knowledge base and RAG MCP tools."""

from mcp.server.fastmcp import FastMCP

from mcp_server.client import get_client
from mcp_server.schemas import (
    GetQuotesInput,
    GetQuotesOutput,
    KnowledgeChunk,
    QuoteItem,
    SearchKnowledgeInput,
    SearchKnowledgeOutput,
)


def register_knowledge_tools(mcp: FastMCP) -> None:
    """Register knowledge base tools with the MCP server."""

    @mcp.tool()
    async def gaobao_search_knowledge(input: SearchKnowledgeInput) -> SearchKnowledgeOutput:  # noqa: N802
        """Search the gaobao-advisor knowledge base using semantic retrieval.

        Performs RAG (Retrieval-Augmented Generation) search over the
        knowledge base to find relevant content about universities, majors,
        policies, and expert advice. Use this for answering questions that
        require domain expertise beyond basic data queries.

        Args:
            input: Search query with optional group filters and result count.

        Returns:
            SearchKnowledgeOutput with relevant knowledge chunks and quotes.
        """
        client = get_client()

        payload = {
            "query": input.query,
            "top_k": input.top_k,
        }
        if input.groups:
            payload["groups"] = input.groups

        data = await client.post("/api/v1/knowledge/search", json_data=payload)

        chunks = []
        for chunk in data.get("chunks", []):
            if isinstance(chunk, dict):
                chunks.append(
                    KnowledgeChunk(
                        content=chunk.get("content", ""),
                        group=chunk.get("group"),
                        source=chunk.get("source"),
                        score=chunk.get("score"),
                    )
                )

        quotes = []
        for quote in data.get("quotes", []):
            if isinstance(quote, dict):
                quotes.append(quote)

        return SearchKnowledgeOutput(
            count=data.get("count", 0),
            groups=data.get("groups", []),
            chunks=chunks,
            quotes=quotes,
        )

    @mcp.tool()
    async def gaobao_get_quotes(input: GetQuotesInput) -> GetQuotesOutput:  # noqa: N802
        """Retrieve expert quotes and golden phrases about universities and careers.

        Returns curated expert quotes that can be used to enrich responses
        with authoritative perspectives on university choices and career paths.

        Args:
            input: Optional major filter and result count.

        Returns:
            GetQuotesOutput with quote items.
        """
        client = get_client()

        params: dict = {"top_k": input.top_k}
        if input.major:
            params["major"] = input.major

        data = await client.get("/api/v1/knowledge/quotes", params=params)

        quotes = []
        for quote in data.get("quotes", []):
            if isinstance(quote, dict):
                quotes.append(
                    QuoteItem(
                        content=quote.get("content", ""),
                        author=quote.get("author"),
                        source=quote.get("source"),
                        tags=quote.get("tags", []),
                    )
                )

        return GetQuotesOutput(
            count=data.get("count", 0),
            quotes=quotes,
        )
