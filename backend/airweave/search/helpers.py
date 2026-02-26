"""Helpers for search."""

from pathlib import Path
from uuid import UUID

import yaml
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api.context import ApiContext
from airweave.schemas.search import SearchResponse
from airweave.schemas.search_query import SearchQueryCreate
from airweave.search.context import SearchContext


class SearchHelpers:
    """Helpers for search."""

    async def persist_search_data(
        self,
        db: AsyncSession,
        search_context: SearchContext,
        search_response: SearchResponse,
        ctx: ApiContext,
        duration_ms: float,
    ) -> None:
        """Persist search data for analytics and user experience.

        Args:
            db: Database session
            search_context: The search context with actual executed configuration
            search_response: The search response
            ctx: API context
            duration_ms: Search execution time in milliseconds
        """
        try:
            # Extract API key ID from auth metadata if available
            api_key_id = None
            if ctx.is_api_key_auth and ctx.auth_metadata:
                api_key_id = ctx.auth_metadata.get("api_key_id")

            # Extract filter from user_filter operation if it was configured
            filter_dict = None
            if search_context.user_filter and search_context.user_filter.filter:
                filter_dict = search_context.user_filter.filter.model_dump(exclude_none=True)

            # Create search query schema using actual values from SearchContext
            # (which has defaults applied via factory)
            search_query_create = SearchQueryCreate(
                collection_id=search_context.collection_id,
                organization_id=ctx.organization.id,
                user_id=ctx.user.id if ctx.user else None,
                api_key_id=UUID(api_key_id) if api_key_id else None,
                query_text=search_context.query,
                query_length=len(search_context.query),
                is_streaming=search_context.stream,
                retrieval_strategy=search_context.retrieval.strategy.value,
                limit=search_context.retrieval.limit,
                offset=search_context.retrieval.offset,
                temporal_relevance=0.0,
                filter=filter_dict,
                duration_ms=int(duration_ms),
                results_count=len(search_response.results),
                expand_query=search_context.query_expansion is not None,
                interpret_filters=search_context.query_interpretation is not None,
                rerank=search_context.reranking is not None,
                generate_answer=search_context.generate_answer is not None,
            )

            # Create search query record using standard CRUD pattern
            await crud.search_query.create(db=db, obj_in=search_query_create, ctx=ctx)

            ctx.logger.debug(
                f"[SearchHelpers] Search data persisted successfully for query: "
                f"'{search_context.query[:50]}...'"
            )

        except Exception as e:
            # Don't fail the search if persistence fails
            ctx.logger.error(
                f"[SearchHelpers] Failed to persist search data: {str(e)}. "
                f"Search completed successfully but analytics data was not saved."
            )

    @staticmethod
    def load_defaults() -> dict:
        """Load search defaults from yaml."""
        path = Path(__file__).with_name("defaults.yml")
        try:
            with path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                raise ValueError("YAML root must be a mapping")
            search_defaults = data.get("search_defaults")
            if not isinstance(search_defaults, dict) or not search_defaults:
                raise ValueError("'search_defaults' missing or empty")
            return data  # Return full data dict with all keys
        except Exception as e:
            raise HTTPException(status_code=500, detail="Failed to load search defaults") from e


search_helpers = SearchHelpers()
