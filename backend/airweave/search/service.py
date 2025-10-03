"""Enhanced search service with configurable operations.

This service uses a modular architecture where search functionality
is broken down into composable operations that can be configured
and executed in a flexible pipeline.
"""

import time

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
        response = await orchestrator.run(ctx, search_context)

        duration_ms = (time.monotonic() - start_time) * 1000
        ctx.logger.debug(f"Search completed in {duration_ms:.2f}ms")

        await search_helpers.persist_search_data(
            db=db,
            search_context=search_context,
            search_response=response,
            ctx=ctx,
            duration_ms=duration_ms,
        )

        # Track search completion to PostHog
        from airweave.analytics.search_analytics import track_search_completion

        # Extract search configuration for analytics
        search_config = {
            "retrieval_strategy": search_context.retrieval.strategy.value,
            "temporal_relevance": (
                search_context.temporal_relevance.weight
                if search_context.temporal_relevance
                else 0.0
            ),
            "expand_query": search_context.query_expansion is not None,
            "interpret_filters": search_context.query_interpretation is not None,
            "rerank": search_context.reranking is not None,
            "generate_answer": search_context.generate_answer is not None,
            "limit": search_context.retrieval.limit,
            "offset": search_context.retrieval.offset,
        }

        # Track the search event
        track_search_completion(
            ctx=ctx,
            query=search_context.query,
            collection_slug=readable_collection_id,
            duration_ms=duration_ms,
            results=response.results,
            completion=response.completion,  # Include AI-generated completion
            search_type="streaming" if stream else "regular",
            status="success",
            **search_config,
        )

        return response


# TODO: clean search results


service = SearchService()
