"""Vector database interface for spotlight search."""

from typing import Protocol

from airweave.search.spotlight.schemas.plan import SpotlightPlan
from airweave.search.spotlight.schemas.query_embeddings import SpotlightQueryEmbeddings
from airweave.search.spotlight.schemas.search_result import SpotlightSearchResults


class SpotlightVectorDBInterface(Protocol):
    """Interface for vector database operations.

    Vector databases compile search plans into DB-specific queries and execute them.
    The compiled query is stored as a string in the state for debugging/transparency.
    """

    async def compile_query(
        self,
        plan: SpotlightPlan,
        embeddings: SpotlightQueryEmbeddings,
        collection_id: str,
    ) -> str:
        """Compile plan and embeddings into a DB-specific query string.

        The returned string format is implementation-specific (e.g., JSON for Vespa).
        It should be self-contained and executable by execute_query().

        Args:
            plan: Search plan with queries, filters, strategy, pagination.
            embeddings: Dense and sparse embeddings for the queries.
            collection_id: Collection readable ID for tenant filtering.

        Returns:
            DB-specific query as a string (e.g., JSON-serialized YQL + params).
        """
        ...

    async def execute_query(
        self,
        compiled_query: str,
    ) -> SpotlightSearchResults:
        """Execute a compiled query and return search results.

        Args:
            compiled_query: The string returned by compile_query().

        Returns:
            Search results container, ordered by relevance.

        Raises:
            RuntimeError: If query execution fails.
        """
        ...

    async def close(self) -> None:
        """Clean up resources (e.g., close connections)."""
        ...
