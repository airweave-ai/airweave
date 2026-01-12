"""Enhanced search service with configurable operations.

This service uses a modular architecture where search functionality
is broken down into composable operations that can be configured
and executed in a flexible pipeline.
"""

import time
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api.context import ApiContext
from airweave.core.exceptions import NotFoundException
from airweave.schemas.search import SearchRequest, SearchResponse
from airweave.search.factory import factory
from airweave.search.helpers import search_helpers
from airweave.search.orchestrator import orchestrator


class SearchService:
    """Search service."""

    async def search(
        self,
        request_id: str,
        readable_collection_id: str,
        search_request: SearchRequest,
        stream: bool,
        db: AsyncSession,
        ctx: ApiContext,
    ) -> SearchResponse:
        """Search a collection."""
        start_time = time.monotonic()

        collection = await crud.collection.get_by_readable_id(
            db, readable_id=readable_collection_id, ctx=ctx
        )
        if not collection:
            raise NotFoundException(detail=f"Collection '{readable_collection_id}' not found")

        ctx.logger.debug("Building search context")
        search_context = await factory.build(
            request_id, collection.id, readable_collection_id, search_request, stream, ctx, db
        )

        ctx.logger.debug("Executing search")
        response, state = await orchestrator.run(ctx, search_context)

        # Handle any federated source auth failures (mark connections as unauthenticated)
        await self._handle_failed_federated_auth(db, state, ctx)

        duration_ms = (time.monotonic() - start_time) * 1000
        ctx.logger.debug(f"Search completed in {duration_ms:.2f}ms")

        # Track search completion to PostHog
        from airweave.analytics.search_analytics import track_search_completion

        # Extract search configuration for analytics
        search_config = {
            "retrieval_strategy": (
                search_context.retrieval.strategy.value if search_context.retrieval else "none"
            ),
            "temporal_relevance": (
                search_context.temporal_relevance.weight
                if search_context.temporal_relevance
                else 0.0
            ),
            "expand_query": search_context.query_expansion is not None,
            "interpret_filters": search_context.query_interpretation is not None,
            "rerank": search_context.reranking is not None,
            "generate_answer": search_context.generate_answer is not None,
            "limit": search_context.retrieval.limit if search_context.retrieval else 0,
            "offset": search_context.retrieval.offset if search_context.retrieval else 0,
        }

        # Track the search event with state for automatic metrics extraction
        # TODO: use background task to track search completion, not blocking the response
        track_search_completion(
            ctx=ctx,
            query=search_context.query,
            collection_slug=readable_collection_id,
            duration_ms=duration_ms,
            results=response.results,
            completion=response.completion,
            search_type="streaming" if stream else "regular",
            status="success",
            state=state,  # Pass state for automatic metrics extraction
            **search_config,
        )

        # Persist search data to database
        # TODO: use background task to persist search data, not blocking the response
        await search_helpers.persist_search_data(
            db=db,
            search_context=search_context,
            search_response=response,
            ctx=ctx,
            duration_ms=duration_ms,
        )

        return response

    async def _handle_failed_federated_auth(
        self,
        db: AsyncSession,
        state: Dict[str, Any],
        ctx: ApiContext,
    ) -> None:
        """Mark source connections as unauthenticated on federated auth errors."""
        failed_conn_ids: List[str] = state.get("_failed_federated_auth", [])
        if not failed_conn_ids:
            return

        for conn_id in failed_conn_ids:
            source_conn = await crud.source_connection.get(db, id=UUID(conn_id), ctx=ctx)
            if source_conn:
                await crud.source_connection.update(
                    db, db_obj=source_conn, obj_in={"is_authenticated": False}, ctx=ctx
                )
                ctx.logger.warning(f"Marked source connection {conn_id} as unauthenticated")


# TODO: clean search results


service = SearchService()
