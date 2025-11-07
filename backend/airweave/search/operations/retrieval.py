"""Retrieval operation.

Performs the actual vector similarity search against Qdrant using embeddings,
filters, and optional temporal decay. This is the core search operation that
queries the vector database.
"""

from typing import Any, Dict, List

from airweave.api.context import ApiContext
from airweave.platform.destinations.qdrant import QdrantDestination
from airweave.schemas.search import RetrievalStrategy
from airweave.search.context import SearchContext

from ._base import SearchOperation


class Retrieval(SearchOperation):
    """Execute vector similarity search in Qdrant."""

    RERANK_PREFETCH_MULTIPLIER = 2.0  # Fetch 2x more candidates for reranking

    def __init__(self, strategy: RetrievalStrategy, offset: int, limit: int) -> None:
        """Initialize with retrieval configuration."""
        self.strategy = strategy
        self.offset = offset
        self.limit = limit

    def depends_on(self) -> List[str]:
        """Depends on operations that provide embeddings, filter, and decay config."""
        return ["QueryInterpretation", "EmbedQuery", "UserFilter", "TemporalRelevance"]

    async def execute(
        self,
        context: SearchContext,
        state: dict[str, Any],
        ctx: ApiContext,
    ) -> None:
        """Execute vector search against Qdrant."""
        ctx.logger.info("[Retrieval] === STARTING QDRANT SEARCH ===")

        # Log access control status if enabled
        if context.access_principals:
            ctx.logger.info(
                f"[Retrieval] ✓ Access control enabled: {len(context.access_principals)} principals"
            )
            ctx.logger.info(f"[Retrieval] Access principals: {context.access_principals}")
        else:
            ctx.logger.warning("[Retrieval] ⚠️  NO ACCESS CONTROL - searching all entities")

        # Get inputs from state (embeddings validated by EmbedQuery)
        dense_embeddings = state.get("dense_embeddings")
        sparse_embeddings = state.get("sparse_embeddings")
        filter_dict = state.get("filter")
        decay_config = state.get("decay_config")
        
        # Log the filter being used for Qdrant query
        ctx.logger.info(f"[Retrieval] Filter from state (to be sent to Qdrant): {filter_dict}")

        # Ensure we have at least one type of embedding
        if dense_embeddings is None and sparse_embeddings is None:
            raise RuntimeError(
                "Retrieval requires embeddings. Ensure EmbedQuery ran or disable Retrieval "
                "for federated-only collections."
            )

        # Determine search method from strategy
        search_method = self._get_search_method()

        # Emit vector search start
        num_embeddings = len(dense_embeddings or sparse_embeddings or [])
        await context.emitter.emit(
            "vector_search_start",
            {
                "method": search_method,
                "embeddings": num_embeddings,
                "has_filter": bool(filter_dict),
                "decay_weight": decay_config.weight if decay_config else None,
            },
            op_name=self.__class__.__name__,
        )

        destination = await QdrantDestination.create(
            collection_id=context.collection_id,
            vector_size=context.vector_size,
            logger=ctx.logger,
        )

        has_reranking = context.reranking is not None
        is_bulk = len(dense_embeddings or sparse_embeddings) > 1

        if is_bulk:
            ctx.logger.debug("[Retrieval] Executing bulk search")
            raw_results = await self._execute_bulk_search(
                destination,
                dense_embeddings,
                sparse_embeddings,
                filter_dict,
                decay_config,
                search_method,
                has_reranking,
                ctx,
            )
        else:
            ctx.logger.debug("[Retrieval] Executing single search")
            raw_results = await self._execute_single_search(
                destination,
                dense_embeddings,
                sparse_embeddings,
                filter_dict,
                decay_config,
                search_method,
                has_reranking,
                ctx,
            )

        paginated_results = self._apply_pagination(raw_results)
        final_count = len(paginated_results)
        if not has_reranking:
            final_results = paginated_results
        else:
            final_results = raw_results  # Pass all to reranking

        # Write to state
        ctx.logger.debug(f"[Retrieval] results: {final_count}")
        state["results"] = final_results

        # Report metrics for analytics
        fetch_limit = self._calculate_fetch_limit(has_reranking, include_offset=True)
        self._report_metrics(
            state,
            output_count=len(raw_results),  # Before pagination
            final_count=final_count,  # After pagination (what gets passed forward)
            search_method=search_method,
            has_filter=bool(filter_dict),
            has_temporal_decay=decay_config is not None,
            decay_weight=decay_config.weight if decay_config else 0.0,
            prefetch_multiplier=self.RERANK_PREFETCH_MULTIPLIER if has_reranking else 1.0,
            actual_fetch_limit=fetch_limit,
            embeddings_used=num_embeddings,
            was_bulk_search=is_bulk,
        )

        # Emit vector search done with stats
        top_scores = [r.get("score", 0) for r in final_results[:3] if isinstance(r, dict)]

        # Add special event if no results found
        if final_count == 0:
            await context.emitter.emit(
                "vector_search_no_results",
                {
                    "reason": "no_matching_documents",
                    "has_filter": bool(filter_dict),
                },
                op_name=self.__class__.__name__,
            )

        await context.emitter.emit(
            "vector_search_done",
            {
                "final_count": final_count,
                "top_scores": top_scores,
            },
            op_name=self.__class__.__name__,
        )

    def _get_search_method(self) -> str:
        """Map RetrievalStrategy to Qdrant search method."""
        mapping = {
            RetrievalStrategy.HYBRID: "hybrid",
            RetrievalStrategy.NEURAL: "neural",
            RetrievalStrategy.KEYWORD: "keyword",
        }
        return mapping[self.strategy]

    def _calculate_fetch_limit(self, has_reranking: bool, include_offset: bool) -> int:
        """Calculate how many results to fetch from Qdrant."""
        base_limit = self.limit
        if include_offset:
            base_limit += self.offset

        if has_reranking:
            # Fetch extra candidates for better reranking
            return int(base_limit * self.RERANK_PREFETCH_MULTIPLIER)

        return base_limit

    async def _execute_single_search(
        self,
        destination: QdrantDestination,
        dense_embeddings: List[List[float]],
        sparse_embeddings: List,
        filter_dict: dict,
        decay_config: Any,
        search_method: str,
        has_reranking: bool,
        ctx: ApiContext,
    ) -> List[Dict]:
        """Execute single query search - always fetch from offset 0."""
        query_vector = dense_embeddings[0] if dense_embeddings else None
        sparse_vector = sparse_embeddings[0] if sparse_embeddings else None

        # Calculate fetch limit (include offset+limit to get all needed candidates)
        fetch_limit = self._calculate_fetch_limit(has_reranking, include_offset=True)

        ctx.logger.debug(f"[Retrieval] Fetch limit: {fetch_limit}")

        results = await destination.search(
            query_vector=query_vector,
            limit=fetch_limit,
            offset=0,  # Always fetch from beginning
            with_payload=True,
            filter=filter_dict,
            sparse_vector=sparse_vector,
            search_method=search_method,
            decay_config=decay_config,
        )

        if not isinstance(results, list):
            raise RuntimeError(f"Expected list of results, got {type(results)}")

        return results

    async def _execute_bulk_search(
        self,
        destination: QdrantDestination,
        dense_embeddings: List[List[float]],
        sparse_embeddings: List,
        filter_dict: dict,
        decay_config: Any,
        search_method: str,
        has_reranking: bool,
        ctx: ApiContext,
    ) -> List[Dict]:
        """Execute bulk search - returns deduplicated results."""
        # Calculate limit (include offset since we apply it after deduplication)
        fetch_limit = self._calculate_fetch_limit(has_reranking, include_offset=True)
        ctx.logger.debug(f"[Retrieval] Fetch limit: {fetch_limit}")

        num_queries = len(dense_embeddings or sparse_embeddings)
        filter_conditions = [filter_dict] * num_queries if filter_dict else None

        results = await destination.bulk_search(
            query_vectors=dense_embeddings or [],
            limit=fetch_limit,
            with_payload=True,
            filter_conditions=filter_conditions,
            sparse_vectors=sparse_embeddings,
            search_method=search_method,
            decay_config=decay_config,
        )

        if not isinstance(results, list):
            raise RuntimeError(f"Expected list of results, got {type(results)}")

        # Deduplicate results (bulk search returns overlapping results from multiple queries)
        deduplicated = self._deduplicate_results(results)

        return deduplicated

    def _deduplicate_results(self, results: List[Dict]) -> List[Dict]:
        """Deduplicate results keeping highest scores."""
        if not results:
            return []

        best_results = {}

        for result in results:
            if not isinstance(result, dict):
                raise ValueError(f"Invalid result type in search results: {type(result)}")

            # Extract document ID
            doc_id = result.get("id") or result.get("_id")

            if not doc_id and "payload" in result:
                payload = result.get("payload", {})
                if isinstance(payload, dict):
                    doc_id = (
                        payload.get("entity_id")
                        or payload.get("id")
                        or payload.get("_id")
                        or payload.get("db_entity_id")
                    )

            if not doc_id:
                raise ValueError(
                    "Search result missing document ID. Cannot deduplicate. "
                    f"Result: {result.keys() if isinstance(result, dict) else result}"
                )

            score = result.get("score", 0)

            # Keep result with highest score
            if doc_id not in best_results or score > best_results[doc_id].get("score", 0):
                best_results[doc_id] = result

        # Convert to list and sort by score
        merged = list(best_results.values())
        merged.sort(key=lambda x: x.get("score", 0), reverse=True)

        return merged

    def _apply_pagination(self, results: List[Dict]) -> List[Dict]:
        """Apply offset and limit (for bulk search after deduplication)."""
        # Apply offset
        if self.offset > 0:
            results = results[self.offset :] if self.offset < len(results) else []

        # Apply limit
        if len(results) > self.limit:
            results = results[: self.limit]

        return results
