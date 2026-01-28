"""Executor for agentic search queries.

Takes a VespaQuery and executes it against Vespa, returning search results.
This is a thin wrapper around VespaClient that handles connection management.
"""

from typing import Optional

from airweave.api.context import ApiContext
from airweave.platform.destinations.vespa.client import VespaClient
from airweave.schemas.search_result import AirweaveSearchResult
from airweave.search.agentic_search.builder.schemas import VespaQuery


class Executor:
    """Executes VespaQuery against Vespa and returns results.

    Manages a VespaClient connection and converts raw Vespa hits
    to AirweaveSearchResult objects.

    Usage:
        executor = Executor(ctx=ctx)
        results = await executor.execute(query)
    """

    def __init__(self, ctx: Optional[ApiContext] = None) -> None:
        """Initialize the executor.

        Args:
            ctx: API context for logging (optional)
        """
        self._ctx = ctx
        self._client: Optional[VespaClient] = None

    def _log(self, message: str, level: str = "debug") -> None:
        """Log a message if context is available."""
        if self._ctx:
            logger = getattr(self._ctx.logger, level)
            logger(f"[Executor] {message}")

    async def _get_client(self) -> VespaClient:
        """Get or create the VespaClient connection.

        Returns:
            Connected VespaClient instance
        """
        if self._client is None:
            logger = self._ctx.logger if self._ctx else None
            self._client = await VespaClient.connect(logger=logger)
            self._log("Connected to Vespa")
        return self._client

    async def execute(self, query: VespaQuery) -> list[AirweaveSearchResult]:
        """Execute a VespaQuery and return search results.

        Args:
            query: VespaQuery with YQL and params

        Returns:
            List of AirweaveSearchResult objects

        Raises:
            RuntimeError: If Vespa query fails
        """
        client = await self._get_client()

        # Execute query
        self._log(f"Executing query ({len(query.yql)} chars)")
        response = await client.execute_query(query.to_query_params())

        # Convert hits to results
        results = client.convert_hits_to_results(response.hits)
        self._log(
            f"Got {len(results)} results "
            f"(total={response.total_count}, coverage={response.coverage_percent:.1f}%)"
        )

        return results

    async def close(self) -> None:
        """Close the VespaClient connection if open."""
        if self._client:
            await self._client.close()
            self._client = None
            self._log("Closed Vespa connection")
