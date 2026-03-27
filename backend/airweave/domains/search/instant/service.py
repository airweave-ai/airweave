"""Instant search service.

Converts request directly into a SearchPlan (no LLM) and executes
via the shared SearchPlanExecutor. Emits lifecycle events.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core.events.search import SearchCompletedEvent, SearchFailedEvent, SearchTier
from airweave.core.exceptions import CollectionNotFoundException, InvalidInputError, NotFoundException
from airweave.core.protocols.event_bus import EventBus
from airweave.domains.collections.protocols import CollectionRepositoryProtocol
from airweave.domains.sources.exceptions import SourceAuthError, SourceCreationError
from airweave.domains.search.protocols import (
    InstantSearchServiceProtocol,
    SearchPlanExecutorProtocol,
)
from airweave.domains.search.types import SearchPlan, SearchQuery, SearchResults
from airweave.domains.source_connections.protocols import SourceConnectionRepositoryProtocol

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
        sc_repo: SourceConnectionRepositoryProtocol,
        event_bus: EventBus,
    ) -> None:
        """Initialize with executor, collection repo, source connection repo, and event bus."""
        self._executor = executor
        self._collection_repo = collection_repo
        self._sc_repo = sc_repo
        self._event_bus = event_bus

    async def search(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        readable_id: str,
        request: InstantSearchRequest,
    ) -> SearchResults:
        """Build plan from request and execute."""
        start_time = time.monotonic()
        ctx.logger.info(f"Instant search started collection={readable_id} query={request.query!r}")

        try:
            result = await self._execute(db, ctx, readable_id, request, start_time)
            duration_ms = int((time.monotonic() - start_time) * 1000)
            ctx.logger.info(
                f"Instant search completed collection={readable_id} "
                f"results={len(result.results)} duration_ms={duration_ms}"
            )
            return result
        except (
            CollectionNotFoundException,
            InvalidInputError,
            SourceAuthError,
            SourceCreationError,
            NotFoundException,
        ):
            # User/config errors — don't emit SearchFailedEvent.
            raise
        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            ctx.logger.error(
                f"Instant search failed collection={readable_id} "
                f"duration_ms={duration_ms} error={e}"
            )
            await self._event_bus.publish(
                SearchFailedEvent(
                    organization_id=ctx.organization.id,
                    request_id=ctx.request_id,
                    tier=SearchTier.INSTANT,
                    plan=ctx.billing_plan,
                    message=str(e),
                    duration_ms=duration_ms,
                )
            )
            raise

    async def _execute(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        readable_id: str,
        request: InstantSearchRequest,
        start_time: float,
    ) -> SearchResults:
        """Internal execution — resolve collection, build plan, execute."""
        collection = await self._collection_repo.get_by_readable_id(db, readable_id, ctx)
        if not collection:
            raise CollectionNotFoundException(f"Collection '{readable_id}' not found")

        source_connections = await self._sc_repo.get_by_collection_ids(
            db,
            organization_id=ctx.organization.id,
            readable_collection_ids=[readable_id],
        )
        if not source_connections:
            raise InvalidInputError(
                f"Collection '{readable_id}' has no sources. "
                "Add a source connection before searching."
            )

        plan = SearchPlan(
            query=SearchQuery(primary=request.query),
            limit=request.limit,
            offset=request.offset,
            retrieval_strategy=request.retrieval_strategy,
        )

        results = await self._executor.execute(
            plan=plan,
            user_filter=request.filter or [],
            collection_id=str(collection.id),
            db=db,
            ctx=ctx,
            collection_readable_id=readable_id,
        )

        duration_ms = int((time.monotonic() - start_time) * 1000)
        await self._event_bus.publish(
            SearchCompletedEvent(
                organization_id=ctx.organization.id,
                request_id=ctx.request_id,
                tier=SearchTier.INSTANT,
                plan=ctx.billing_plan,
                results=[r.model_dump(mode="json") for r in results.results],
                duration_ms=duration_ms,
            )
        )

        return results
