"""Classic search service.

Single LLM call generates a search strategy (query expansions, retrieval strategy,
optional filters), then execute via the shared SearchPlanExecutor, optionally rerank.
Target latency: 2-5s.
"""

from __future__ import annotations

import functools
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core.events.search import SearchCompletedEvent, SearchFailedEvent, SearchTier
from airweave.core.protocols.event_bus import EventBus
from airweave.core.protocols.llm import LLMProtocol
from airweave.core.protocols.reranker import RerankerProtocol
from airweave.domains.collections.protocols import CollectionRepositoryProtocol
from airweave.domains.search.classic.types import ClassicSearchStrategy
from airweave.domains.search.messages import _load_overview, build_system_prompt
from airweave.domains.search.persistence import persist_v2_search_query
from airweave.domains.search.protocols import (
    ClassicSearchServiceProtocol,
    CollectionMetadataBuilderProtocol,
    SearchPlanExecutorProtocol,
)
from airweave.domains.search.types import SearchPlan, SearchResults
from airweave.domains.search.types.filters import format_filter_groups_md

if TYPE_CHECKING:
    from airweave.schemas.search_v2 import ClassicSearchRequest


@functools.cache
def _load_classic_task() -> str:
    """Load and cache the classic task prompt."""
    return (Path(__file__).parent / "context" / "classic_task.md").read_text()


class ClassicSearchService(ClassicSearchServiceProtocol):
    """Classic search — one LLM call generates a smart search strategy, then execute."""

    def __init__(
        self,
        llm: LLMProtocol,
        reranker: Optional[RerankerProtocol],
        executor: SearchPlanExecutorProtocol,
        collection_repo: CollectionRepositoryProtocol,
        metadata_builder: CollectionMetadataBuilderProtocol,
        event_bus: EventBus,
    ) -> None:
        """Initialize with LLM, reranker, executor, collection repo, metadata builder, event bus."""
        self._llm = llm
        self._reranker = reranker
        self._executor = executor
        self._collection_repo = collection_repo
        self._metadata_builder = metadata_builder
        self._event_bus = event_bus

    async def search(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        readable_id: str,
        request: ClassicSearchRequest,
    ) -> SearchResults:
        """Generate strategy via LLM, execute, optionally rerank, return results."""
        start_time = time.monotonic()
        ctx.logger.info(f"Classic search started collection={readable_id} query={request.query!r}")

        try:
            result = await self._execute(db, ctx, readable_id, request, start_time)
            duration_ms = int((time.monotonic() - start_time) * 1000)
            ctx.logger.info(
                f"Classic search completed collection={readable_id} "
                f"results={len(result.results)} duration_ms={duration_ms}"
            )
            return result
        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            ctx.logger.error(
                f"Classic search failed collection={readable_id} "
                f"duration_ms={duration_ms} error={e}"
            )
            await self._event_bus.publish(
                SearchFailedEvent(
                    organization_id=ctx.organization.id,
                    request_id=ctx.request_id,
                    tier=SearchTier.CLASSIC,
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
        request: ClassicSearchRequest,
        start_time: float,
    ) -> SearchResults:
        """Internal execution — resolve collection, LLM strategy, search, rerank."""
        # 1. Resolve collection
        collection = await self._collection_repo.get_by_readable_id(db, readable_id, ctx)
        if not collection:
            raise HTTPException(status_code=404, detail=f"Collection '{readable_id}' not found")

        # 2. Build system prompt
        metadata = await self._metadata_builder.build(db, ctx, readable_id)
        system_prompt = build_system_prompt(
            overview=_load_overview(),
            task=_load_classic_task(),
            metadata=metadata,
        )

        # 3. LLM generates strategy (no limit/offset — those come from the request)
        user_filter_md = format_filter_groups_md(request.filter) if request.filter else "None"
        prompt = f"User query: {request.query}\nUser filter: {user_filter_md}"
        strategy = await self._llm.structured_output(prompt, ClassicSearchStrategy, system_prompt)
        ctx.logger.debug(
            f"Classic search LLM strategy primary={strategy.query.primary!r} "
            f"retrieval={strategy.retrieval_strategy} "
            f"filter_groups={len(strategy.filter_groups or [])}"
        )

        # Guard: if LLM returned an empty or non-word primary query, fall back to the
        # user's original. LLMs sometimes return "", ".", or punctuation-only strings.
        if not strategy.query.primary or not any(c.isalnum() for c in strategy.query.primary):
            ctx.logger.warning(
                f"Classic search LLM returned empty/invalid primary query, "
                f"falling back to user query={request.query!r}"
            )
            strategy.query.primary = request.query

        # 4. Combine with request.limit/offset → full SearchPlan
        plan = SearchPlan(
            query=strategy.query,
            retrieval_strategy=strategy.retrieval_strategy,
            filter_groups=strategy.filter_groups,
            limit=request.limit,
            offset=request.offset,
        )

        # 5. Execute
        results = await self._executor.execute(
            plan=plan,
            user_filter=request.filter or [],
            collection_id=str(collection.id),
            db=db,
            ctx=ctx,
            collection_readable_id=readable_id,
        )

        # 6. Optional rerank
        if self._reranker and results.results:
            documents = [r.textual_representation for r in results.results]
            reranked = await self._reranker.rerank(
                query=request.query,
                documents=documents,
                top_n=request.limit,
            )
            results = SearchResults(results=[results.results[r.index] for r in reranked])

        # 7. Emit event + return
        duration_ms = int((time.monotonic() - start_time) * 1000)
        await self._event_bus.publish(
            SearchCompletedEvent(
                organization_id=ctx.organization.id,
                request_id=ctx.request_id,
                tier=SearchTier.CLASSIC,
                plan=ctx.billing_plan,
                results=[r.model_dump(mode="json") for r in results.results],
                duration_ms=duration_ms,
                collection_id=UUID(str(collection.id)),
            )
        )

        await persist_v2_search_query(
            db,
            ctx,
            collection_id=UUID(str(collection.id)),
            query_text=request.query,
            retrieval_strategy="classic",
            is_streaming=False,
            limit=request.limit,
            offset=request.offset,
            duration_ms=duration_ms,
            results_count=len(results.results),
            filter_groups=[f.model_dump() for f in request.filter] if request.filter else None,
            expand_query=True,
            interpret_filters=True,
            rerank=self._reranker is not None,
        )

        return results
