"""Vector database interface for spotlight search."""

from typing import Protocol

from airweave.search.spotlight.schemas.compiled_query import SpotlightCompiledQuery
from airweave.search.spotlight.schemas.plan import SpotlightPlan
from airweave.search.spotlight.schemas.query_embeddings import SpotlightQueryEmbeddings
from airweave.search.spotlight.schemas.search_result import SpotlightSearchResults


class SpotlightVectorDBInterface(Protocol):
    """Interface for vector database operations.

    Vector databases compile search plans into DB-specific queries and execute them.
    The compiled query contains both the raw query (for execution) and a display
    version (for logging/history, without embeddings).
    """

    async def compile_query(
        self,
        plan: SpotlightPlan,
        embeddings: SpotlightQueryEmbeddings,
        collection_id: str,
    ) -> SpotlightCompiledQuery:
        """Compile plan and embeddings into a DB-specific query.

        Args:
            plan: Search plan with queries, filters, strategy, pagination.
            embeddings: Dense and sparse embeddings for the queries.
            collection_id: Collection readable ID for tenant filtering.

        Returns:
            SpotlightCompiledQuery with:
            - vector_db: Name of the vector database
            - display: Human-readable query (no embeddings)
            - raw: Full query for execution (via .raw property)
        """
        ...

    async def execute_query(
        self,
        compiled_query: SpotlightCompiledQuery,
    ) -> SpotlightSearchResults:
        """Execute a compiled query and return search results.

        Args:
            compiled_query: The SpotlightCompiledQuery from compile_query().
                Uses compiled_query.raw for the actual query execution.

        Returns:
            Search results container, ordered by relevance.

        Raises:
            RuntimeError: If query execution fails.
        """
        ...

    async def close(self) -> None:
        """Clean up resources (e.g., close connections)."""
        ...
