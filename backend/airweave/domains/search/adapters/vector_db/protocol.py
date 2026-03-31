"""Vector database protocol for the search module."""

from typing import Optional, Protocol

from airweave.domains.search.types.embeddings import QueryEmbeddings
from airweave.domains.search.types.filters import FilterGroup
from airweave.domains.search.types.plan import SearchPlan
from airweave.domains.search.types.results import (
    CompiledQuery,
    SearchResult,
    SearchResults,
)


class VectorDBProtocol(Protocol):
    """Protocol for vector database operations.

    Vector databases compile search plans into DB-specific queries and execute them.
    """

    async def compile_query(
        self,
        plan: SearchPlan,
        embeddings: QueryEmbeddings,
        collection_id: str,
        acl_principals: Optional[list[str]] = None,
    ) -> CompiledQuery:
        """Compile plan and embeddings into a DB-specific query.

        Args:
            plan: Search plan with queries, filters, strategy, pagination.
            embeddings: Dense and sparse embeddings for the queries.
            collection_id: Collection readable ID for tenant filtering.
            acl_principals: Resolved user principals for access control filtering.
                None = no AC sources in collection (skip filtering).
                [] = user has no principals (only public entities visible).
                ["user:x", "group:y"] = match these principals.

        Returns:
            CompiledQuery with raw (full) and display (no embeddings) versions.
        """
        ...

    async def execute_query(
        self,
        compiled_query: CompiledQuery,
    ) -> SearchResults:
        """Execute a compiled query and return search results.

        Args:
            compiled_query: The CompiledQuery from compile_query().

        Returns:
            Search results container, ordered by relevance.
        """
        ...

    async def count(
        self,
        filter_groups: list[FilterGroup],
        collection_id: str,
    ) -> int:
        """Count entities matching filters without retrieving content.

        Args:
            filter_groups: Filter groups to narrow the count.
            collection_id: Collection readable ID for tenant filtering.

        Returns:
            Total number of matching entities.
        """
        ...

    async def filter_search(
        self,
        filter_groups: list[FilterGroup],
        collection_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SearchResult]:
        """Retrieve entities matching filters without embeddings or ranking.

        Args:
            filter_groups: Filter groups to narrow results.
            collection_id: Collection readable ID for tenant filtering.
            limit: Maximum number of results to return.
            offset: Number of results to skip.

        Returns:
            List of matching results (unranked).
        """
        ...

    async def close(self) -> None:
        """Clean up resources (e.g., close connections)."""
        ...
