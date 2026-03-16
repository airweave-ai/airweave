"""Instant search service.

Converts request directly into a SearchPlan (no LLM) and executes
via the shared SearchPlanExecutor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.domains.collections.protocols import CollectionRepositoryProtocol
from airweave.domains.search.protocols import (
    InstantSearchServiceProtocol,
    SearchPlanExecutorProtocol,
)
from airweave.domains.search.types import SearchPlan, SearchQuery, SearchResults

if TYPE_CHECKING:
    from airweave.schemas.search_v2 import InstantSearchRequest


class InstantSearchService(InstantSearchServiceProtocol):
    """Instant search — convert request to plan, execute against Vespa.

    No LLM involved. The user's query becomes the plan directly.
    """

    def __init__(
        self,
        executor: SearchPlanExecutorProtocol,
        collection_repo: CollectionRepositoryProtocol,
    ) -> None:
        """Initialize with executor and collection repo for readable_id -> UUID resolution."""
        self._executor = executor
        self._collection_repo = collection_repo

    async def search(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        readable_id: str,
        request: InstantSearchRequest,
    ) -> SearchResults:
        """Build plan from request and execute."""
        # Resolve readable_id -> collection UUID (Vespa indexes by UUID)
        collection = await self._collection_repo.get_by_readable_id(db, readable_id, ctx)
        if not collection:
            raise HTTPException(status_code=404, detail=f"Collection '{readable_id}' not found")

        plan = SearchPlan(
            query=SearchQuery(primary=request.query),
            limit=request.limit,
            offset=request.offset,
            retrieval_strategy=request.retrieval_strategy,
        )
        return await self._executor.execute(
            plan=plan,
            user_filter=request.filter or [],
            collection_id=str(collection.id),
        )
