"""Instant search service.

Converts request directly into a SearchPlan (no LLM) and executes
via the shared SearchPlanExecutor. Emits SearchCompletedEvent on success.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core.events.search import SearchCompletedEvent
from airweave.core.protocols.event_bus import EventBus
from airweave.domains.collections.protocols import CollectionRepositoryProtocol
from airweave.domains.search.protocols import (
    InstantSearchServiceProtocol,
    SearchPlanExecutorProtocol,
)
from airweave.domains.search.types import SearchPlan, SearchQuery, SearchResults
from airweave.schemas.search_v2 import SearchTier

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
        event_bus: EventBus,
    ) -> None:
        """Initialize with executor, collection repo, and event bus."""
        self._executor = executor
        self._collection_repo = collection_repo
        self._event_bus = event_bus

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

        start = time.monotonic()
        results = await self._executor.execute(
            plan=plan,
            user_filter=request.filter or [],
            collection_id=str(collection.id),
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        await self._event_bus.publish(
            SearchCompletedEvent(
                organization_id=ctx.organization.id,
                request_id=ctx.request_id,
                tier=SearchTier.INSTANT.value,
                results=[r.model_dump(mode="json") for r in results.results],
                duration_ms=duration_ms,
            )
        )

        return results
