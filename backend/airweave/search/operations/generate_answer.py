"""Answer generation operation.

Generates natural language answers from search results using LLM.
Synthesizes information from multiple results into a coherent response
with inline citations.
"""

from typing import TYPE_CHECKING, Dict, List

from airweave.api.context import ApiContext
from airweave.search.context import SearchContext
from airweave.search.prompts import GENERATE_ANSWER_SYSTEM_PROMPT
from airweave.search.providers._base import BaseProvider

from ._base import SearchOperation

if TYPE_CHECKING:
    from airweave.search.state import SearchState


class GenerateAnswer(SearchOperation):
    """Generate AI completion from search results."""

    MAX_COMPLETION_TOKENS = 10000
    SAFETY_TOKENS = 2000

    def __init__(self, providers: List[BaseProvider]) -> None:
        """Initialize with list of LLM providers in preference order.

        Args:
            providers: List of LLM providers for answer generation with fallback support
        """
        if not providers:
            raise ValueError("GenerateAnswer requires at least one provider")
        self.providers = providers

    def depends_on(self) -> List[str]:
        """Depends on Retrieval, FederatedSearch (if enabled), and Reranking to have all results."""
        return ["Retrieval", "FederatedSearch", "Reranking"]

    async def execute(
        self,
        context: SearchContext,
        state: "SearchState",
        ctx: ApiContext,
    ) -> None:
        """Generate natural language answer from results."""
        ctx.logger.debug("[GenerateAnswer] Generating natural language answer from results")

        results = state.results

        if not results:
            state.completion = "No results found for your query."
            ctx.logger.debug("[GenerateAnswer] INPUT: No results to process")
            return

        if not isinstance(results, list):
            raise ValueError(f"Expected 'results' to be a list, got {type(results)}")

        # DEBUG: Log input
        sample_results = []
        for r in results[:3]:
            name = r.get("name", "N/A")
            text = r.get("textual_representation", "")
            sample_results.append(
                {
                    "name": name[:50] if name else "N/A",
                    "text_preview": (text[:100] if text else "") + "...",
                }
            )
        ctx.logger.debug(
            f"\n[GenerateAnswer] INPUT:\n"
            f"  Query: '{context.query[:100]}...'\n"
            f"  Results count: {len(results)}\n"
            f"  Providers: {[p.__class__.__name__ for p in self.providers]}\n"
            f"  Sample results (first 3): {sample_results}\n"
        )

        # Emit completion start
        # Note: Model name not included since we don't know which provider will succeed yet
        await context.emitter.emit(
            "completion_start",
            {},
            op_name=self.__class__.__name__,
        )

        # Generate answer with provider fallback
        # Token budgeting happens per-provider since context windows differ
        chosen_count_for_metrics = 0  # Track for metrics

        async def call_provider(provider: BaseProvider) -> str:
            nonlocal chosen_count_for_metrics

            if not provider.model_spec.llm_model:
                raise RuntimeError("LLM model not configured for provider")

            # Budget and format results for THIS SPECIFIC provider
            formatted_context, chosen_count = self._budget_and_format_results(
                results, context.query, provider, ctx
            )
            chosen_count_for_metrics = chosen_count  # Store for metrics

            # DEBUG: Log context window details
            context_window = provider.model_spec.llm_model.context_window
            tokenizer = getattr(provider, "llm_tokenizer", None)
            context_tokens = provider.count_tokens(formatted_context, tokenizer) if tokenizer else 0
            ctx.logger.debug(
                f"\n[GenerateAnswer] CONTEXT WINDOW ({provider.__class__.__name__}):\n"
                f"  Model: {provider.model_spec.llm_model.name}\n"
                f"  Context window: {context_window:,} tokens\n"
                f"  Results fitting in budget: {chosen_count}/{len(results)}\n"
                f"  Context tokens used: ~{context_tokens:,}\n"
                f"  Max completion tokens: {self.MAX_COMPLETION_TOKENS:,}\n"
                f"  Formatted context preview (first 500 chars):\n"
                f"    {formatted_context[:500]}...\n"
            )

            # Build messages for LLM
            system_prompt = GENERATE_ANSWER_SYSTEM_PROMPT.format(context=formatted_context)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context.query},
            ]

            return await provider.generate(messages)

        completion = await self._execute_with_provider_fallback(
            providers=self.providers,
            operation_call=call_provider,
            operation_name="GenerateAnswer",
            ctx=ctx,
            state=state,
        )

        if not completion or not completion.strip():
            raise RuntimeError("Provider returned empty completion")

        state.completion = completion

        # DEBUG: Log output
        ctx.logger.debug(
            f"\n[GenerateAnswer] OUTPUT:\n"
            f"  Completion length: {len(completion)} chars (~{len(completion) // 4} tokens)\n"
            f"  Completion preview (first 300 chars):\n"
            f"    {completion[:300]}...\n"
        )

        # Report metrics for analytics
        # Approximate token count (rough estimate: 1 token ≈ 4 characters)
        completion_tokens = len(completion) // 4
        self._report_metrics(
            state,
            context_documents=chosen_count_for_metrics,
            completion_tokens=completion_tokens,
            completion_length=len(completion),
        )

        # Emit completion done
        await context.emitter.emit(
            "completion_done",
            {"text": completion},
            op_name=self.__class__.__name__,
        )

    def _budget_and_format_results(
        self, results: List[Dict], query: str, provider: BaseProvider, ctx: ApiContext
    ) -> tuple[str, int]:
        """Format results while respecting token budget for specific provider.

        Args:
            results: Search results to format
            query: User query
            provider: The actual provider that will be used (not a random one!)
            ctx: API context for logging

        Returns:
            Tuple of (formatted_context, chosen_count)
        """
        tokenizer = getattr(provider, "llm_tokenizer", None)
        if not tokenizer:
            raise RuntimeError(
                "LLM tokenizer not initialized. "
                "Ensure tokenizer is configured in defaults.yml for this provider."
            )

        context_window = provider.model_spec.llm_model.context_window
        if not context_window:
            raise RuntimeError("Context window not configured for LLM model")

        static_text = GENERATE_ANSWER_SYSTEM_PROMPT.format(context="") + query
        static_tokens = provider.count_tokens(static_text, tokenizer)

        budget = context_window - static_tokens - self.MAX_COMPLETION_TOKENS - self.SAFETY_TOKENS

        if budget <= 0:
            raise RuntimeError(
                f"Insufficient token budget for answer generation. "
                f"Context window: {context_window}, static tokens: {static_tokens}"
            )

        # Fit as many results as possible within budget
        separator = "\n\n---\n\n"
        chosen_parts: List[str] = []
        chosen_count = 0
        running_tokens = 0

        for i, result in enumerate(results):
            formatted_result = self._format_single_result(i + 1, result, ctx)
            result_tokens = provider.count_tokens(formatted_result, tokenizer)
            separator_tokens = provider.count_tokens(separator, tokenizer) if i > 0 else 0

            if running_tokens + result_tokens + separator_tokens <= budget:
                if i > 0:
                    chosen_parts.append(separator)
                chosen_parts.append(formatted_result)
                running_tokens += result_tokens + separator_tokens
                chosen_count += 1
            else:
                break

        # Ensure at least one result if possible
        if not chosen_parts and results:
            first_result = self._format_single_result(1, results[0], ctx)
            first_tokens = provider.count_tokens(first_result, tokenizer)
            if first_tokens <= budget:
                return first_result, 1
            raise RuntimeError(
                f"First result ({first_tokens} tokens) exceeds token budget ({budget} tokens). "
                "Results may be too large or context window too small."
            )

        return "".join(chosen_parts), chosen_count

    def _format_single_result(self, index: int, result: Dict, ctx: ApiContext) -> str:
        """Format a single search result for LLM context.

        In the unified AirweaveSearchResult schema, textual_representation is a
        top-level required field. Legacy fields may exist in source_fields for
        backward compatibility.

        Args:
            index: Result index (1-based)
            result: Single search result dict (serialized AirweaveSearchResult)
            ctx: API context for logging

        Returns:
            Formatted string with entity ID and textual representation
        """
        score = result.get("score", 0.0)

        # Extract entity ID (top-level in AirweaveSearchResult)
        entity_id = result.get("entity_id") or f"result_{index}"

        # textual_representation is a top-level required field in AirweaveSearchResult
        content = result.get("textual_representation", "").strip()

        # Fallback to source_fields for legacy entities
        if not content:
            source_fields = result.get("source_fields", {})
            if isinstance(source_fields, dict):
                content = (
                    source_fields.get("embeddable_text", "").strip()
                    or source_fields.get("md_content", "").strip()
                    or source_fields.get("content", "").strip()
                    or source_fields.get("text", "").strip()
                    or source_fields.get("description", "").strip()
                    or ""
                )

        if not content:
            # Ultimate fallback: stringify the entire result
            # This ensures answer generation never fails, even for malformed entities
            content = str(result)
            ctx.logger.warning(
                f"[GenerateAnswer] Result {index} (entity {entity_id}) missing "
                f"textual_representation. Using str(result) fallback."
            )

        # Build formatted entry with score and content
        return f"### Result {index} - Entity ID: [[{entity_id}]] (Score: {score:.3f})\n\n{content}"
