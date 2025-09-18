"""Search service for vector database integrations."""

import json
from datetime import datetime
from typing import Any

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core.config import settings
from airweave.core.exceptions import NotFoundException
from airweave.platform.destinations._base import BaseDestination
from airweave.platform.embedding_models._base import BaseEmbeddingModel
from airweave.platform.embedding_models.bm25_text2vec import BM25Text2Vec
from airweave.platform.embedding_models.local_text2vec import LocalText2Vec
from airweave.platform.embedding_models.openai_text2vec import OpenAIText2Vec
from airweave.platform.locator import resource_locator
from airweave.schemas.search import (
    QueryExpansionStrategy,
    ResponseType,
    SearchRequest,
    SearchStatus,
)
from airweave.search.decay import DecayConfig


class SearchService:
    """Service for handling vector database searches."""

    # OpenAI configuration constants
    DEFAULT_MODEL = "gpt-5-nano"
    DEFAULT_MODEL_SETTINGS = {
        "temperature": 0.7,
        "max_tokens": 10000,
        "top_p": 1,
        "frequency_penalty": 0,
        "presence_penalty": 0,
    }

    CONTEXT_PROMPT = """You are an AI assistant with access to a knowledge base.
    Use the following relevant context to help answer the user's question.
    Always format your responses in proper markdown, including:
    - Using proper headers (# ## ###)
    - Formatting code blocks with ```language
    - Using tables with | header | header |
    - Using bullet points and numbered lists
    - Using **bold** and *italic* where appropriate

    Here's the context:
    {context}

    Remember to:
    1. Be helpful, clear, and accurate
    2. Maintain a professional tone
    3. Format ALL responses in proper markdown
    4. Use tables when presenting structured data
    5. Use code blocks with proper language tags"""

    def __init__(self):
        """Initialize the search service with OpenAI client."""
        if not settings.OPENAI_API_KEY:
            self.openai_client = None
        else:
            self.openai_client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
            )

    def _clean_search_results(self, results: list[dict]) -> list[dict]:
        """Clean search results by removing large fields and parsing JSON strings.

        Args:
            results: Raw search results from vector database

        Returns:
            Cleaned search results
        """
        cleaned_results = []

        for result in results:
            if not isinstance(result, dict):
                cleaned_results.append(result)
                continue

            cleaned_result = result.copy()

            # Remove the id field from the result
            cleaned_result.pop("id", None)

            if "payload" in cleaned_result and isinstance(cleaned_result["payload"], dict):
                payload = cleaned_result["payload"].copy()

                # Always remove these fields - they're too large or unnecessary
                fields_to_always_remove = [
                    "vector",
                    "download_url",
                    "local_path",
                    "file_uuid",
                    "checksum",
                    "sync_id",
                    "sync_job_id",
                    # Hide embeddable_text in RAW results; still available for LLM context
                    "embeddable_text",
                ]
                for field in fields_to_always_remove:
                    payload.pop(field, None)

                # Handle nested JSON strings - parse them for better display
                json_fields = ["metadata", "sync_metadata", "auth_fields", "config_fields"]
                for field in json_fields:
                    if field in payload and isinstance(payload[field], str):
                        try:
                            # Try to parse JSON string to object for better display
                            payload[field] = json.loads(payload[field])
                        except json.JSONDecodeError:
                            # If it's not valid JSON, keep as is
                            pass

                cleaned_result["payload"] = payload

            cleaned_results.append(cleaned_result)

        return cleaned_results

    def _merge_search_results(
        self, all_results: list[dict], ctx: ApiContext, max_results: int = 15
    ) -> list[dict]:
        """Merge and deduplicate search results from multiple query expansions.

        Deduplicates by document ID, keeping the highest score for each unique document.
        Results are re-sorted by score in descending order.

        Args:
            all_results (list[dict]): Combined results from multiple search queries
            ctx (ApiContext): The API context
            max_results (int): Maximum number of results to return

        Returns:
            list[dict]: Deduplicated and sorted results
        """
        if not all_results:
            return []

        best_results = {}

        for result in all_results:
            doc_id = None
            if isinstance(result, dict):
                doc_id = result.get("id") or result.get("_id")
                if not doc_id and "payload" in result:
                    payload = result.get("payload", {})
                    doc_id = payload.get("entity_id") or payload.get("id") or payload.get("_id")

            if doc_id:
                # Get current score
                score = result.get("score", 0)

                # Keep result with highest score
                if doc_id not in best_results or score > best_results[doc_id].get("score", 0):
                    best_results[doc_id] = result
            else:
                # If we can't find an ID, include the result anyway
                # Use a unique key based on result position
                unique_key = f"no_id_{len(best_results)}_{id(result)}"
                best_results[unique_key] = result

        # Convert back to list and sort by score
        merged = list(best_results.values())
        merged.sort(key=lambda x: x.get("score", 0), reverse=True)

        # Optionally limit results to maintain performance
        if len(merged) > max_results:
            merged = merged[:max_results]

        ctx.logger.info(f"Merged {len(all_results)} results into {len(merged)} unique documents")

        return merged

    async def _execute_search(
        self,
        db: AsyncSession,
        query: str,
        readable_id: str,
        ctx: ApiContext,
        expansion_strategy: QueryExpansionStrategy | None = None,
        filter: Any | None = None,  # Add filter parameter
        limit: int = 10,  # Add limit parameter
        offset: int = 0,  # Add offset parameter
        score_threshold: float | None = None,  # Add score threshold
    ) -> list[dict]:
        """Internal method to execute search and return raw results.

        This is the single source of truth for search execution, avoiding duplication.

        Args:
            db (AsyncSession): Database session
            query (str): Search query text
            readable_id (str): Readable ID of the collection to search within
            ctx (ApiContext): The API context
            expansion_strategy (QueryExpansionStrategy | None): Query expansion strategy.
                If None, no expansion is performed.
            filter: Qdrant filter for metadata filtering
            limit: Maximum number of results
            offset: Number of results to skip
            score_threshold: Minimum score threshold

        Returns:
            list[dict]: Raw search results (not cleaned)
        """
        # Get collection and validate
        collection = await self._get_collection(db, readable_id, ctx)

        # Get destination for vector search
        destination_class = await self._get_destination_class(db)
        destination = await destination_class.create(collection_id=collection.id, logger=ctx.logger)

        # Get appropriate embedding models
        embedding_model = self._get_embedding_model(collection, ctx)

        # Load keyword indexing model if destination has/supports it
        keyword_indexing_model = None
        if await destination.has_keyword_index():
            keyword_indexing_model = self._get_keyword_indexing_model(ctx)

        # Perform search based on query expansion strategy
        if expansion_strategy and expansion_strategy != QueryExpansionStrategy.NO_EXPANSION:
            return await self._search_with_expansion(
                query,
                expansion_strategy,
                embedding_model,
                keyword_indexing_model,
                destination,
                ctx.logger,
                filter=filter,
                limit=limit,
                offset=offset,
                score_threshold=score_threshold,
            )

        return await self._search_single_query(
            query,
            embedding_model,
            keyword_indexing_model,
            destination,
            ctx.logger,
            filter=filter,
            limit=limit,
            offset=offset,
            score_threshold=score_threshold,
        )

    async def search(
        self,
        db: AsyncSession,
        query: str,
        readable_id: str,
        ctx: ApiContext,
        response_type: ResponseType = ResponseType.RAW,
        expansion_strategy: QueryExpansionStrategy | None = None,
    ) -> schemas.SearchResponse:
        """Search across vector database and optionally generate AI completion.

        Args:
            db: Database session
            query: Search query text
            readable_id: Readable ID of the collection to search within
            ctx: The API context
            response_type: Type of response (raw results or AI completion)
            expansion_strategy: Query expansion strategy. If None, no expansion.

        Returns:
            SearchResponse: Search results with optional AI completion

        Raises:
            NotFoundException: If sync or connections not found
            ConnectionError: If unable to connect to vector database
        """
        try:
            # Execute the search once
            raw_results = await self._execute_search(
                db=db,
                query=query,
                readable_id=readable_id,
                ctx=ctx,
                expansion_strategy=expansion_strategy,
            )

            # Clean results
            cleaned_results = self._clean_search_results(raw_results)

            if response_type == ResponseType.RAW:
                return schemas.SearchResponse(
                    results=cleaned_results,
                    response_type=response_type,
                    status=SearchStatus.SUCCESS,
                )

            # Check for no results or low-quality results
            quality_response = self._check_result_quality(cleaned_results)
            if quality_response:
                return quality_response

            # Process results and generate completion
            processed_results = self._process_search_results(cleaned_results)
            # Pass embeddable_text back into context for the LLM by injecting it
            # (the cleaned_results already have it removed; fetch raw to supply context)
            completion = await self._generate_ai_completion(query, raw_results)

            return schemas.SearchResponse(
                results=processed_results,
                completion=completion,
                response_type=response_type,
                status=SearchStatus.SUCCESS,
            )

        except NotFoundException:
            # Re-raise NotFoundExceptions as-is, will be handled by the middleware
            raise
        except Exception as e:
            ctx.logger.error(f"Search error: {str(e)}", exc_info=True)
            # Add more context to the error
            if "connection" in str(e).lower():
                raise ConnectionError(f"Vector database connection failed: {str(e)}") from e
            raise

    async def search_with_request(
        self,
        db: AsyncSession,
        readable_id: str,
        search_request: SearchRequest,
        ctx: ApiContext,
    ) -> schemas.SearchResponse:
        """Search with comprehensive SearchRequest parameters.

        Args:
            db: Database session
            readable_id: Readable ID of the collection to search within
            search_request: SearchRequest with all parameters
            ctx: The API context

        Returns:
            SearchResponse: Search results with optional AI completion
        """
        try:
            # Execute the search with all parameters from SearchRequest
            raw_results = await self._execute_search(
                db=db,
                query=search_request.query,
                readable_id=readable_id,
                ctx=ctx,
                expansion_strategy=search_request.expansion_strategy,
                filter=search_request.filter,
                limit=search_request.limit,
                offset=search_request.offset,
                score_threshold=search_request.score_threshold,
            )

            # Clean results based on include_metadata and with_vectors flags
            cleaned_results = self._clean_search_results(raw_results)

            # Always remove vectors from results
            for result in cleaned_results:
                if isinstance(result, dict) and "payload" in result:
                    result["payload"].pop("vector", None)

            if search_request.response_type == ResponseType.RAW:
                return schemas.SearchResponse(
                    results=cleaned_results,
                    response_type=search_request.response_type,
                    status=SearchStatus.SUCCESS,
                )

            # Check for no results or low-quality results
            quality_response = self._check_result_quality(cleaned_results)
            if quality_response:
                return quality_response

            # Process results and generate completion
            processed_results = self._process_search_results(cleaned_results)

            completion = await self._generate_ai_completion(search_request.query, raw_results)

            return schemas.SearchResponse(
                results=processed_results,
                completion=completion,
                response_type=search_request.response_type,
                status=SearchStatus.SUCCESS,
            )

        except NotFoundException:
            raise
        except Exception as e:
            ctx.logger.error(f"Search error: {str(e)}", exc_info=True)
            if "connection" in str(e).lower():
                raise ConnectionError(f"Vector database connection failed: {str(e)}") from e
            raise

    async def _get_collection(
        self, db: AsyncSession, readable_id: str, ctx: ApiContext
    ) -> schemas.Collection:
        """Get collection by readable ID and validate it exists."""
        collection = await crud.collection.get_by_readable_id(db, readable_id, ctx)
        if not collection:
            raise NotFoundException("Collection not found")
        return collection

    async def _get_destination_class(self, db: AsyncSession):
        """Get the destination class for vector database operations."""
        destination_model = await crud.destination.get_by_short_name(db, "qdrant_native")
        if not destination_model:
            raise NotFoundException("Destination not found")
        return resource_locator.get_destination(destination_model)

    def _get_embedding_model(
        self, collection: schemas.Collection, ctx: ApiContext
    ) -> BaseEmbeddingModel:
        """Get the appropriate embedding model based on collection's vector size."""
        from airweave.core.collection_service import get_embedding_model_for_collection
        
        return get_embedding_model_for_collection(collection, ctx.logger)

    def _get_keyword_indexing_model(self, ctx: ApiContext) -> BaseEmbeddingModel:
        """Get the appropriate keyword embedding model based on configuration."""
        return BM25Text2Vec(ctx.logger)

    async def _search_with_expansion(
        self,
        query: str,
        expansion_strategy: QueryExpansionStrategy,
        embedding_model: BaseEmbeddingModel,
        keyword_indexing_model: BaseEmbeddingModel | None,
        destination: BaseDestination,
        ctx: ApiContext,
        filter: Any | None = None,
        limit: int = 10,
        offset: int = 0,
        score_threshold: float | None = None,
    ) -> list[dict]:
        """Perform search with query expansion."""
        from airweave.search.operations.query_expansion import QueryExpansion

        # Use QueryExpansion for compatibility
        query_expander = QueryExpansion(strategy=expansion_strategy)

        # Create a minimal context for the operation
        temp_context = {
            "query": query,
            "config": type("Config", (), {"expansion_strategy": expansion_strategy})(),
            "logger": ctx.logger,
        }

        # Execute the expansion
        await query_expander.execute(temp_context)
        expanded_queries = temp_context.get("expanded_queries", [query])
        ctx.logger.info(
            f"Expanded query '{query}' to {len(expanded_queries)} variants "
            f"using {expansion_strategy.value} strategy"
        )

        # Embed all expanded queries
        vectors = await embedding_model.embed_many(expanded_queries)
        sparse_embeddings = None
        if keyword_indexing_model:
            sparse_embeddings = await keyword_indexing_model.embed_many(expanded_queries)

        # Convert filter to dict if it's a Qdrant Filter object
        filter_dict = None
        if filter:
            if hasattr(filter, "model_dump"):
                filter_dict = filter.model_dump(exclude_none=True)
            else:
                filter_dict = filter

        # Use bulk search for all expanded queries at once
        # Create filter conditions list (same filter for all queries)
        filter_conditions = [filter_dict] * len(vectors) if filter_dict else None

        batch_results = await destination.bulk_search(
            vectors,
            limit=limit,
            score_threshold=score_threshold,
            with_payload=True,
            filter_conditions=filter_conditions,
            sparse_vectors=list(sparse_embeddings) if sparse_embeddings else None,
            # TODO: Determine an optimal default for this
            search_method="hybrid",
            decay_config=DecayConfig(
                decay_type="linear",
                datetime_field="created_time",
                target_datetime=datetime.now(),
                scale_unit="year",
                scale_value=1.0,
                midpoint=0.5,
            ),
        )

        # Apply offset after merging (since bulk search doesn't support offset)
        merged_results = self._merge_search_results(
            batch_results, max_results=limit + offset, ctx=ctx
        )

        # Apply offset
        if offset > 0 and offset < len(merged_results):
            merged_results = merged_results[offset:]
        elif offset >= len(merged_results):
            merged_results = []

        # Ensure we don't exceed limit
        if len(merged_results) > limit:
            merged_results = merged_results[:limit]

        return merged_results

    async def _search_single_query(
        self,
        query: str,
        embedding_model: BaseEmbeddingModel,
        keyword_indexing_model: BaseEmbeddingModel | None,
        destination: BaseDestination,
        ctx: ApiContext,
        filter: Any | None = None,
        limit: int = 10,
        offset: int = 0,
        score_threshold: float | None = None,
    ) -> list[dict]:
        """Perform search with a single query (no expansion)."""
        vector = await embedding_model.embed(query)
        sparse_embeddings = None
        if keyword_indexing_model:
            sparse_embeddings = await keyword_indexing_model.embed(query)

        # Convert filter to dict if it's a Qdrant Filter object
        filter_dict = None
        if filter:
            if hasattr(filter, "model_dump"):
                filter_dict = filter.model_dump(exclude_none=True)
            else:
                filter_dict = filter

        return await destination.search(
            vector,
            filter=filter_dict,
            limit=limit,
            offset=offset,
            score_threshold=score_threshold,
            with_payload=True,
            sparse_vector=list(sparse_embeddings)[0] if sparse_embeddings else None,
        )

    def _check_result_quality(self, results: list[dict]) -> schemas.SearchResponse | None:
        """Check if results are empty or have low quality scores.

        Returns:
            SearchResponse if results are poor quality, None if results are good
        """
        # If no results found, return a more specific message
        if not results:
            return schemas.SearchResponse(
                results=[],
                completion=(
                    "I couldn't find any relevant information for that query. "
                    "Try asking about something in your data collection."
                ),
                response_type=ResponseType.COMPLETION,
                status=SearchStatus.NO_RESULTS,
            )

        # For low-quality results (where scores are low), add this check:
        has_relevant_results = any(result.get("score", 0) > 0.25 for result in results)
        if not has_relevant_results:
            return schemas.SearchResponse(
                results=results,
                completion=(
                    "Your query didn't match anything meaningful in the database. "
                    "Please try a different question related to your data."
                ),
                response_type=ResponseType.COMPLETION,
                status=SearchStatus.NO_RELEVANT_RESULTS,
            )

        return None

    def _process_search_results(self, results: list[dict]) -> list[dict]:
        """Process search results by removing vector data and download URLs.

        Args:
            results: Raw search results

        Returns:
            Processed results with vectors and download URLs removed
        """
        for result in results:
            if isinstance(result, dict) and "payload" in result:
                # Remove vector from payload to avoid sending large data back
                result["payload"].pop("vector", None)
                # Also remove download URLs from payload
                result["payload"].pop("download_url", None)

        return results

    async def _generate_ai_completion(self, query: str, context_results: list[dict]) -> str:
        """Generate AI completion based on search results.

        Args:
            query: The user's search query
            context_results: Processed search results for context

        Returns:
            AI-generated completion text
        """
        # Prepare messages for OpenAI
        messages = [
            {
                "role": "system",
                "content": self.CONTEXT_PROMPT.format(
                    context=str(context_results),
                    additional_instruction=(
                        "If the provided context doesn't contain information to answer "
                        "the query directly, respond with 'I don't have enough information to "
                        "answer that question based on the available data.'"
                    ),
                ),
            },
            {"role": "user", "content": query},
        ]

        # Generate completion
        model = self.DEFAULT_MODEL
        model_settings = self.DEFAULT_MODEL_SETTINGS.copy()

        # Remove streaming setting if present
        model_settings.pop("stream", None)

        try:
            if not self.openai_client:
                return "OpenAI API key not configured. Cannot generate completion."

            response = await self.openai_client.chat.completions.create(
                model=model, messages=messages, **model_settings
            )

            return (
                response.choices[0].message.content
                if response.choices
                else "Unable to generate completion."
            )
        except Exception as e:
            return f"Error generating completion: {str(e)}"


# Create singleton instance
search_service = SearchService()
