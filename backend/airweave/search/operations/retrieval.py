"""Retrieval operation.

Performs the actual search against the configured destination using the
destination-agnostic search interface. This is the core search operation that
queries the vector database (Qdrant, Vespa, or future destinations).
"""

from typing import Any, Dict, List

from airweave.api.context import ApiContext
from airweave.platform.destinations._base import BaseDestination
from airweave.schemas.search import RetrievalStrategy, SearchResult
from airweave.search.context import SearchContext

from ._base import SearchOperation


class Retrieval(SearchOperation):
    """Execute search against the configured destination."""

    RERANK_PREFETCH_MULTIPLIER = 2.0  # Fetch 2x more candidates for reranking

    def __init__(
        self,
        destination: BaseDestination,
        strategy: RetrievalStrategy,
        offset: int,
        limit: int,
    ) -> None:
        """Initialize with retrieval configuration.

        Args:
            destination: The destination instance to search against
            strategy: Search strategy (hybrid, neural, keyword)
            offset: Number of results to skip (pagination)
            limit: Maximum number of results to return
        """
        self.destination = destination
        self.strategy = strategy
        self.offset = offset
        self.limit = limit

    def depends_on(self) -> List[str]:
        """Depends on operations that may provide embeddings, filter, and decay config.

        Note: EmbedQuery may not run for destinations that embed server-side (e.g., Vespa).
        In that case, embeddings will be None in state and the destination handles it.
        """
        return ["QueryInterpretation", "EmbedQuery", "UserFilter", "TemporalRelevance"]

    async def execute(
        self,
        context: SearchContext,
        state: dict[str, Any],
        ctx: ApiContext,
    ) -> None:
        """Execute search against the destination."""
        ctx.logger.debug("[Retrieval] Executing search")

        # Get inputs from state (may be None for server-side embedding destinations)
        dense_embeddings = state.get("dense_embeddings")
        sparse_embeddings = state.get("sparse_embeddings")
        filter_obj = state.get("filter")
        temporal_config = state.get("temporal_config")

        # Determine search strategy from strategy enum
        retrieval_strategy = self._get_search_method()

        # Check if this is a bulk search (multiple query expansions)
        is_bulk = dense_embeddings and len(dense_embeddings) > 1
        num_embeddings = len(dense_embeddings) if dense_embeddings else 0

        # DEBUG: Log inputs
        expanded_queries = state.get("expanded_queries", [])
        ctx.logger.debug(
            f"\n[Retrieval] INPUT:\n"
            f"  Original query: '{context.query[:100]}...'\n"
            f"  Expanded queries: {expanded_queries}\n"
            f"  Dense embeddings: {num_embeddings} x "
            f"{len(dense_embeddings[0]) if dense_embeddings else 0}-dim\n"
            f"  Sparse embeddings: {'yes' if sparse_embeddings else 'no'}\n"
            f"  Filter: {filter_obj}\n"
            f"  Temporal config: {temporal_config}\n"
            f"  Strategy: {retrieval_strategy}\n"
            f"  Destination: {self.destination.__class__.__name__}\n"
        )

        # Emit vector search start
        await context.emitter.emit(
            "vector_search_start",
            {
                "method": retrieval_strategy,
                "embeddings": num_embeddings,
                "has_filter": filter_obj is not None,
                "temporal_weight": temporal_config.weight if temporal_config else None,
            },
            op_name=self.__class__.__name__,
        )

        has_reranking = context.reranking is not None

        # Calculate fetch limit
        fetch_limit = self._calculate_fetch_limit(has_reranking, include_offset=True)
        ctx.logger.debug(f"[Retrieval] Fetch limit: {fetch_limit}")

        # Build queries list - includes original query plus any expanded queries
        # If query expansion ran, state may have expanded_queries; otherwise use original
        expanded_queries = state.get("expanded_queries", [])
        queries = [context.query] + expanded_queries if expanded_queries else [context.query]

        # Execute search via destination interface
        raw_results = await self.destination.search(
            queries=queries,
            airweave_collection_id=context.collection_id,
            limit=fetch_limit,
            offset=0,  # We handle pagination ourselves for deduplication
            filter=filter_obj,
            dense_embeddings=dense_embeddings,
            sparse_embeddings=sparse_embeddings,
            retrieval_strategy=retrieval_strategy,
            temporal_config=temporal_config,
        )

        # Convert SearchResult objects to dicts for downstream compatibility
        results_as_dicts = self._results_to_dicts(raw_results)

        # For bulk search (query expansion), deduplicate results
        if is_bulk:
            results_as_dicts = self._deduplicate_results(results_as_dicts)

        # Apply pagination
        paginated_results = self._apply_pagination(results_as_dicts)
        final_count = len(paginated_results)

        # Pass all results to reranking if enabled, otherwise use paginated
        if has_reranking:
            final_results = results_as_dicts  # Pass all to reranking
        else:
            final_results = paginated_results

        # Write to state
        state["results"] = final_results

        # DEBUG: Log output with sample results
        sample_results = []
        for r in final_results[:3]:
            payload = r.get("payload", {})
            sample_results.append(
                {
                    "name": payload.get("name", "N/A")[:50],
                    "entity_type": payload.get("airweave_system_metadata_entity_type", "N/A"),
                    "score": r.get("score", 0),
                }
            )
        ctx.logger.debug(
            f"\n[Retrieval] OUTPUT:\n"
            f"  Raw results from destination: {len(raw_results)}\n"
            f"  After dedup (if bulk): {len(results_as_dicts)}\n"
            f"  After pagination: {final_count}\n"
            f"  Passed to next stage: {len(final_results)} (reranking={has_reranking})\n"
            f"  Top 3 results: {sample_results}\n"
        )

        # Report metrics for analytics
        self._report_metrics(
            state,
            output_count=len(results_as_dicts),
            final_count=final_count,
            search_method=retrieval_strategy,
            has_filter=filter_obj is not None,
            has_temporal_decay=temporal_config is not None,
            decay_weight=temporal_config.weight if temporal_config else 0.0,
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
                    "has_filter": filter_obj is not None,
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
        """Map RetrievalStrategy to search method string."""
        mapping = {
            RetrievalStrategy.HYBRID: "hybrid",
            RetrievalStrategy.NEURAL: "neural",
            RetrievalStrategy.KEYWORD: "keyword",
        }
        return mapping[self.strategy]

    def _calculate_fetch_limit(self, has_reranking: bool, include_offset: bool) -> int:
        """Calculate how many results to fetch from destination."""
        base_limit = self.limit
        if include_offset:
            base_limit += self.offset

        if has_reranking:
            # Fetch extra candidates for better reranking
            return int(base_limit * self.RERANK_PREFETCH_MULTIPLIER)

        return base_limit

    def _results_to_dicts(self, results: List[SearchResult]) -> List[Dict[str, Any]]:
        """Convert SearchResult objects to dicts for downstream compatibility.

        Args:
            results: List of SearchResult objects

        Returns:
            List of result dictionaries
        """
        return [
            {
                "id": r.id,
                "score": r.score,
                "payload": r.payload,
            }
            for r in results
        ]

    def _deduplicate_results(self, results: List[Dict]) -> List[Dict]:
        """Deduplicate results keeping highest scores.

        Used when multiple query expansions return overlapping results.
        """
        if not results:
            return []

        best_results: Dict[str, Dict] = {}

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
