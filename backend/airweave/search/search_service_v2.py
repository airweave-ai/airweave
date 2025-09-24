"""Enhanced search service with configurable operations.

This service uses a modular architecture where search functionality
is broken down into composable operations that can be configured
and executed in a flexible pipeline.
"""

import time
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api.context import ApiContext
from airweave.core.exceptions import NotFoundException
from airweave.schemas.search import SearchConfig, SearchRequest, SearchResponse, SearchStatus
from airweave.schemas.search_query import SearchQueryCreate
from airweave.search.config_builder import SearchConfigBuilder
from airweave.search.executor import SearchExecutor


class SearchServiceV2:
    """Enhanced search service with modular operations.

    This service orchestrates search operations using a configurable
    pipeline. The pipeline is built based on the search request and
    executed in dependency order.
    """

    def __init__(self):
        """Initialize the search service."""
        self.config_builder = SearchConfigBuilder()
        self.executor = SearchExecutor()

        # Resolve Pydantic forward references for SearchConfig operation fields at runtime.
        # We import the operation classes here (runtime, not at type-check time) and then
        # rebuild the model so that string forward refs like "QueryInterpretation" resolve.
        try:
            from airweave.search.operations.completion import CompletionGeneration  # noqa: F401
            from airweave.search.operations.embedding import Embedding  # noqa: F401
            from airweave.search.operations.qdrant_filter import (
                QdrantFilterOperation,  # noqa: F401
            )
            from airweave.search.operations.query_expansion import QueryExpansion  # noqa: F401
            from airweave.search.operations.query_interpretation import (
                QueryInterpretation,  # noqa: F401
            )
            from airweave.search.operations.recency_bias import RecencyBias  # noqa: F401
            from airweave.search.operations.reranking import LLMReranking  # noqa: F401
            from airweave.search.operations.vector_search import VectorSearch  # noqa: F401

            # Rebuild the model to resolve forward references now that classes are imported
            SearchConfig.model_rebuild()
        except Exception:
            # If anything goes wrong, we don't fail service init; errors would surface on use
            pass

    async def search_with_request(
        self,
        db: AsyncSession,
        readable_id: str,
        search_request: SearchRequest,
        ctx: ApiContext,
        request_id: Optional[str] = None,
    ) -> SearchResponse:
        """Execute search with the given request.

        This is the main entry point for search. It:
        1. Validates the collection exists and user has access
        2. Builds a SearchConfig with execution plan from the request
        3. Executes the operations in dependency order
        4. Builds and returns the response
        5. Persists search data for analytics

        Args:
            db: Database session
            readable_id: Collection readable ID
            search_request: Search request with query and parameters
            ctx: API context with logger and auth
            request_id: Optional streaming request identifier. When provided, the executor
                will emit lifecycle and data events to ``search:<request_id>``.

        Returns:
            SearchResponse with results and optional completion

        Raises:
            NotFoundException: If collection not found or no access
        """
        start_time = time.monotonic()

        ctx.logger.info(
            f"[SearchServiceV2] Starting search for collection '{readable_id}', "
            f"query: '{search_request.query[:50]}...'"
        )

        # Get collection to validate access and get ID
        collection = await self._get_collection(db, readable_id, ctx)

        # Build config with execution plan
        config = self.config_builder.build(search_request, str(collection.id), ctx)

        # Execute the search pipeline
        # Count enabled operations for logging
        enabled_count = sum(
            [
                config.query_interpretation is not None,
                config.query_expansion is not None,
                config.qdrant_filter is not None,
                1,  # embedding (always present)
                1,  # vector_search (always present)
                config.reranking is not None,
                config.completion is not None,
            ]
        )
        ctx.logger.info(
            f"[SearchServiceV2] Executing search pipeline with {enabled_count} operations"
        )
        context = await self.executor.execute(config, db, ctx, request_id=request_id)

        # Build response from execution context
        response = self._build_response(context, search_request, config)

        # Calculate search duration
        duration_ms = (time.monotonic() - start_time) * 1000

        ctx.logger.info(
            f"[SearchServiceV2] Search completed with status: {response.status}, "
            f"results: {len(response.results)}, duration: {duration_ms:.2f}ms"
        )

        # Persist search data for analytics
        await self._persist_search_data(
            db=db,
            search_request=search_request,
            search_response=response,
            collection_id=collection.id,
            ctx=ctx,
            duration_ms=duration_ms,
            collection_slug=readable_id,
        )

        return response

    async def _get_collection(self, db: AsyncSession, readable_id: str, ctx: ApiContext) -> any:
        """Get collection and validate access.

        Args:
            db: Database session
            readable_id: Collection readable ID
            ctx: API context

        Returns:
            Collection object

        Raises:
            NotFoundException: If not found or no access
        """
        collection = await crud.collection.get_by_readable_id(db, readable_id=readable_id, ctx=ctx)
        if not collection:
            raise NotFoundException(detail=f"Collection '{readable_id}' not found")
        return collection

    def _build_response(
        self, context: dict, search_request: SearchRequest, config: SearchConfig
    ) -> SearchResponse:
        """Build search response from execution context.

        Args:
            context: Execution context with results
            search_request: Original search request
            config: Search configuration

        Returns:
            SearchResponse with appropriate status
        """
        # Get results from context
        results = context.get("final_results", [])

        # Clean results (remove vectors, etc.)
        cleaned_results = self._clean_results(results)

        # Determine status
        if not cleaned_results:
            status = SearchStatus.NO_RESULTS
        elif all(r.get("score", 0) < 0.5 for r in cleaned_results):
            # If all scores are low, mark as no relevant results
            status = SearchStatus.NO_RELEVANT_RESULTS
        else:
            status = SearchStatus.SUCCESS

        # Build response
        response = SearchResponse(
            results=cleaned_results,
            response_type=search_request.response_type,
            completion=context.get("completion"),
            status=status,
        )

        return response

    def _clean_results(self, results: list) -> list:
        """Clean search results for response.

        Removes internal fields like vectors and sensitive data.

        Args:
            results: Raw search results

        Returns:
            Cleaned results
        """
        import json

        cleaned = []
        for result in results:
            # Make a copy to avoid modifying original
            clean_result = dict(result)

            # Remove internal fields
            fields_to_remove = ["id", "_id", "vector"]
            for field in fields_to_remove:
                clean_result.pop(field, None)

            # Clean payload if it exists
            if "payload" in clean_result:
                payload = clean_result["payload"]

                # Remove sensitive/internal fields from payload
                sensitive_fields = [
                    "vector",
                    "download_url",
                    "local_path",
                    "file_uuid",
                    "checksum",
                    "sync_id",
                    "sync_job_id",
                    "embeddable_text",
                ]
                for field in sensitive_fields:
                    payload.pop(field, None)

                # Parse JSON strings in certain fields
                json_fields = ["metadata", "sync_metadata", "auth_fields", "config_fields"]
                for field in json_fields:
                    if field in payload and isinstance(payload[field], str):
                        try:
                            payload[field] = json.loads(payload[field])
                        except (json.JSONDecodeError, TypeError):
                            pass

            cleaned.append(clean_result)

        return cleaned

    async def _persist_search_data(
        self,
        db: AsyncSession,
        search_request: SearchRequest,
        search_response: SearchResponse,
        collection_id: str,
        ctx: ApiContext,
        duration_ms: float,
        collection_slug: str,
    ) -> None:
        """Persist search data for analytics and user experience.

        Args:
            db: Database session
            search_request: The search request object
            search_response: The search response object
            collection_id: ID of the collection that was searched
            ctx: API context with user and organization info
            duration_ms: Search execution time in milliseconds
            collection_slug: Collection readable ID for analytics
        """
        try:
            # Convert collection_id to UUID if it's a string

            collection_uuid = (
                UUID(collection_id) if isinstance(collection_id, str) else collection_id
            )

            # Determine search status
            status = self._determine_search_status(search_response)

            # Extract API key ID from auth metadata if available
            api_key_id = None
            if ctx.is_api_key_auth and ctx.auth_metadata:
                api_key_id = ctx.auth_metadata.get("api_key_id")

            # Create search query schema following the standard pattern
            search_query_create = SearchQueryCreate(
                collection_id=collection_uuid,
                organization_id=ctx.organization.id,
                user_id=ctx.user.id if ctx.user else None,
                api_key_id=UUID(api_key_id) if api_key_id else None,
                query_text=search_request.query,
                query_length=len(search_request.query),
                search_type=self._determine_search_type(search_request),
                response_type=(
                    search_request.response_type.value if search_request.response_type else None
                ),
                limit=search_request.limit,
                offset=search_request.offset,
                score_threshold=search_request.score_threshold,
                recency_bias=search_request.recency_bias,
                search_method=search_request.search_method,
                filters=search_request.filter.model_dump() if search_request.filter else None,
                duration_ms=int(duration_ms),
                results_count=len(search_response.results),
                status=status,
                query_expansion_enabled=(
                    search_request.expansion_strategy != "no_expansion"
                    if search_request.expansion_strategy
                    else None
                ),
                reranking_enabled=(
                    search_request.enable_reranking
                    if search_request.enable_reranking is not None
                    else None
                ),
                query_interpretation_enabled=(
                    search_request.enable_query_interpretation
                    if search_request.enable_query_interpretation is not None
                    else None
                ),
            )

            # Create search query record using standard CRUD pattern
            await crud.search_query.create(db=db, obj_in=search_query_create, ctx=ctx)

            ctx.logger.debug(
                f"[SearchServiceV2] Search data persisted successfully for query: "
                f"'{search_request.query[:50]}...'"
            )

        except Exception as e:
            # Don't fail the search if persistence fails
            ctx.logger.error(
                f"[SearchServiceV2] Failed to persist search data: {str(e)}. "
                f"Search completed successfully but analytics data was not saved."
            )

    def _determine_search_status(self, search_response: SearchResponse) -> str:
        """Determine search status from response.

        Args:
            search_response: The search response object

        Returns:
            Status string: 'success', 'no_results', 'no_relevant_results', 'error'
        """
        if search_response.status == SearchStatus.SUCCESS:
            return "success"
        elif search_response.status == SearchStatus.NO_RESULTS:
            return "no_results"
        elif search_response.status == SearchStatus.NO_RELEVANT_RESULTS:
            return "no_relevant_results"
        else:
            return "error"

    def _determine_search_type(self, search_request: SearchRequest) -> str:
        """Determine search type based on request parameters.

        Args:
            search_request: The search request object

        Returns:
            Search type string
        """
        # Check if it's a streaming search (would need additional context)
        # For now, we'll determine based on request complexity
        if search_request.filter or search_request.score_threshold or search_request.recency_bias:
            return "advanced"
        return "basic"


# Singleton instance
search_service_v2 = SearchServiceV2()
