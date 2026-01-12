"""Reranking operation.

Provider-agnostic reranking that reorders retrieval results using the
`rerank` capability of the configured provider. The provider is responsible
for handling its own constraints (token windows, max docs, truncation).
This operation:
  - Reads `results` from state (produced by `Retrieval`)
  - Prepares provider documents from result payloads
  - Calls provider.rerank(query, documents, top_n)
  - Applies the returned ranking to reorder results
  - Writes reordered list back to `state["results"]`
"""

from typing import Any, Dict, List

from airweave.api.context import ApiContext
from airweave.search.context import SearchContext
from airweave.search.providers._base import BaseProvider

from ._base import SearchOperation


class Reranking(SearchOperation):
    """Rerank search results using LLM for improved relevance."""

    def __init__(self, providers: List[BaseProvider]) -> None:
        """Initialize with list of LLM providers in preference order.

        Args:
            providers: List of LLM providers for reranking with fallback support
        """
        if not providers:
            raise ValueError("Reranking requires at least one provider")
        self.providers = providers

    def depends_on(self) -> List[str]:
        """Depends on Retrieval and FederatedSearch (if enabled) to have all results merged."""
        return ["Retrieval", "FederatedSearch"]

    async def execute(  # noqa: C901
        self,
        context: SearchContext,
        state: dict[str, Any],
        ctx: ApiContext,
    ) -> None:
        """Rerank results using the configured provider."""
        ctx.logger.debug("[Reranking] Reranking results")

        results = state.get("results")

        if results is None:
            raise RuntimeError(
                "Reranking requires results produced by Retrieval or FederatedSearch"
            )
        if not isinstance(results, list):
            raise ValueError(f"Expected 'results' to be a list, got {type(results)}")
        if len(results) == 0:
            state["results"] = []
            return

        # Get offset and limit from retrieval operation if present, otherwise from context
        offset = context.retrieval.offset if context.retrieval else context.offset
        limit = context.retrieval.limit if context.retrieval else context.limit

        # DEBUG: Log input
        sample_docs_preview = []
        for r in results[:3]:
            payload = r.get("payload", {})
            text = payload.get("textual_representation", "")[:100]
            sample_docs_preview.append(f"{payload.get('name', 'N/A')[:30]}: {text}...")
        ctx.logger.debug(
            f"\n[Reranking] INPUT:\n"
            f"  Query: '{context.query[:100]}...'\n"
            f"  Results to rerank: {len(results)}\n"
            f"  Offset: {offset}, Limit: {limit}\n"
            f"  Providers: {[p.__class__.__name__ for p in self.providers]}\n"
            f"  Sample docs (first 3):\n    - " + "\n    - ".join(sample_docs_preview) + "\n"
        )

        # Track k/top_n value across provider attempts
        final_top_n = None

        # Rerank with provider fallback
        # Document preparation and top_n calculation happen per-provider
        async def call_provider(provider: BaseProvider) -> List[Dict[str, Any]]:
            nonlocal final_top_n

            # Prepare inputs for THIS SPECIFIC provider (max_docs varies by provider)
            documents, top_n = self._prepare_inputs_for_provider(
                context, results, provider, offset, limit, ctx
            )

            if not documents:
                raise RuntimeError(
                    f"Document preparation produced no documents from {len(results)} results. "
                    "This indicates a bug in document extraction logic."
                )

            # Emit reranking start with actual k value on first attempt
            if final_top_n is None:
                final_top_n = top_n
                await context.emitter.emit(
                    "reranking_start",
                    {"k": top_n},
                    op_name=self.__class__.__name__,
                )

            return await provider.rerank(context.query, documents, top_n)

        rankings = await self._execute_with_provider_fallback(
            providers=self.providers,
            operation_call=call_provider,
            operation_name="Reranking",
            ctx=ctx,
            state=state,
        )

        # DEBUG: Log rankings from provider
        ctx.logger.debug(
            f"[Reranking] RANKINGS FROM PROVIDER:\n"
            f"  Total rankings: {len(rankings) if rankings else 0}\n"
            f"  Top 5 rankings: {rankings[:5] if rankings else 'None'}"
        )

        if not isinstance(rankings, list) or not rankings:
            raise RuntimeError("Provider returned empty or invalid rankings")

        # Emit rankings snapshot
        await context.emitter.emit(
            "rankings",
            {"rankings": rankings},
            op_name=self.__class__.__name__,
        )

        # Apply rankings, then apply offset and limit to the reranked results
        # Use the top_n from the provider that actually succeeded
        if final_top_n is None:
            raise RuntimeError("top_n was never set - this should not happen")
        reranked = self._apply_rankings(results, rankings, final_top_n)

        # Apply pagination after reranking to ensure consistent offset behavior
        paginated = self._apply_pagination(reranked, offset, limit)

        state["results"] = paginated

        # DEBUG: Log output
        reranked_preview = []
        for r in paginated[:5]:
            payload = r.get("payload", {})
            reranked_preview.append(
                f"{payload.get('name', 'N/A')[:40]} (score={r.get('score', 0):.4f})"
            )
        ctx.logger.debug(
            f"\n[Reranking] OUTPUT:\n"
            f"  Reranked count: {len(reranked)}\n"
            f"  After pagination: {len(paginated)}\n"
            f"  Top 5 reranked:\n    - " + "\n    - ".join(reranked_preview) + "\n"
        )

        # Report metrics for analytics
        # Check if we hit provider max_docs limit
        provider_max_docs = None
        if self.providers and self.providers[0].model_spec.rerank_model:
            provider_max_docs = self.providers[0].model_spec.rerank_model.max_documents

        self._report_metrics(
            state,
            input_count=len(results),  # How many results sent to reranker
            output_count=len(reranked),  # After reranking, before pagination
            final_count=len(paginated),  # After pagination
            k_value=final_top_n,
            provider_max_docs=provider_max_docs,
            capped_to_limit=provider_max_docs and len(results) > provider_max_docs,
        )

        # Emit reranking done
        await context.emitter.emit(
            "reranking_done",
            {
                "rankings": rankings,
                "applied": bool(rankings),
            },
            op_name=self.__class__.__name__,
        )

    def _prepare_inputs_for_provider(
        self,
        context: SearchContext,
        results: List[dict],
        provider: BaseProvider,
        offset: int,
        limit: int,
        ctx: ApiContext,
    ) -> tuple[List[str], int]:
        """Prepare documents for reranking for specific provider.

        Args:
            context: Search context
            results: Results to rerank
            provider: The actual provider that will be used (not random!)
            offset: Pagination offset
            limit: Pagination limit
            ctx: API context for logging

        Returns:
            Tuple of (documents, top_n)
        """
        if not results:
            return [], 0

        # Get THIS provider's max_documents limit if configured (varies by provider!)
        max_docs = None
        if provider.model_spec.rerank_model:
            max_docs = provider.model_spec.rerank_model.max_documents

        # Cap results to provider's limit if specified
        if max_docs and len(results) > max_docs:
            results_to_rerank = results[:max_docs]
            ctx.logger.debug(
                f"[Reranking] Capping to {max_docs} results for {provider.__class__.__name__}"
            )
        else:
            results_to_rerank = results

        documents = self._prepare_documents(results_to_rerank, ctx)

        top_n = min(len(documents), offset + limit)

        if top_n < 1:
            raise ValueError("Computed top_n < 1 for reranking")

        ctx.logger.debug(
            f"[Reranking] top_n={top_n} (offset={offset}, limit={limit}, "
            f"provider={provider.__class__.__name__})"
        )
        return documents, top_n

    def _prepare_documents(self, results: List[dict], ctx: ApiContext) -> List[str]:
        """Extract textual_representation from result payloads.

        textual_representation already contains formatted content from entity_pipeline.py,
        so we use it directly without building document strings.

        For backward compatibility with old entities, falls back to embeddable_text and
        other legacy fields if textual_representation is missing.
        """
        documents: List[str] = []
        for i, result in enumerate(results):
            if not isinstance(result, dict):
                raise ValueError(f"Result at index {i} is not a dict: {type(result)}")
            payload = result.get("payload", {})
            if not isinstance(payload, dict):
                payload = {}

            # Try new field first (present in all newly synced entities)
            doc = payload.get("textual_representation", "").strip()

            # Fallback to legacy fields for old entities (pre-refactor)
            if not doc:
                doc = (
                    payload.get("embeddable_text", "").strip()
                    or payload.get("md_content", "").strip()
                    or payload.get("content", "").strip()
                    or payload.get("text", "").strip()
                    or ""
                )

            if not doc:
                # Ultimate fallback: stringify the entire payload
                # This ensures reranking never fails, even for malformed entities
                doc = str(payload)
                ctx.logger.warning(
                    f"[Reranking] Result at index {i} missing textual content fields. "
                    f"Using str(payload) fallback. Entity ID: {payload.get('entity_id', 'unknown')}"
                )
            documents.append(doc)

        return documents

    def _apply_rankings(self, results: List[dict], rankings: List[dict], top_n: int) -> List[dict]:
        ranked_indices = self._validate_and_extract_indices(rankings, len(results))

        seen = set()
        ordered: List[dict] = []
        for idx in ranked_indices:
            if idx not in seen:
                ordered.append(results[idx])
                seen.add(idx)

        for i, r in enumerate(results):
            if len(ordered) >= top_n:
                break
            if i not in seen:
                ordered.append(r)

        return ordered[:top_n]

    def _validate_and_extract_indices(self, rankings: List[dict], results_len: int) -> List[int]:
        """Extract and validate ranking indices."""
        indices: List[int] = []
        for item in rankings:
            if not isinstance(item, dict):
                raise ValueError("Ranking item must be a dict with 'index' and 'relevance_score'")
            if "index" not in item:
                raise ValueError("Ranking item missing 'index'")
            idx = int(item["index"])
            if idx < 0 or idx >= results_len:
                raise IndexError("Ranking index out of bounds")
            indices.append(idx)
        return indices

    def _apply_pagination(self, results: List[dict], offset: int, limit: int) -> List[dict]:
        """Apply offset and limit to reranked results."""
        # Apply offset
        if offset > 0:
            results = results[offset:] if offset < len(results) else []

        # Apply limit
        if len(results) > limit:
            results = results[:limit]

        return results
