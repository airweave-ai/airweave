"""Enhanced search service with configurable operations.

This service uses a modular architecture where search functionality
is broken down into composable operations that can be configured
and executed in a flexible pipeline.
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api.context import ApiContext
from airweave.core.exceptions import NotFoundException
from airweave.schemas.search import SearchConfig, SearchRequest, SearchResponse, SearchStatus
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

        ctx.logger.info(
            f"[SearchServiceV2] Search completed with status: {response.status}, "
            f"results: {len(response.results)}"
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


# Singleton instance
search_service_v2 = SearchServiceV2()
