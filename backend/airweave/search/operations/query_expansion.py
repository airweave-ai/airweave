"""Query expansion operation.

Expands the user's query into multiple variations to improve recall.
Uses LLM to generate semantic alternatives that might match relevant documents
using different terminology while preserving the original search intent.
"""

from typing import Any, List

from pydantic import BaseModel, Field

from airweave.api.context import ApiContext
from airweave.search.context import SearchContext
from airweave.search.prompts import QUERY_EXPANSION_SYSTEM_PROMPT
from airweave.search.providers._base import BaseProvider

from ._base import SearchOperation

# Number of query expansion alternatives to generate (module-level for Pydantic model)
_NUMBER_OF_EXPANSIONS = 4


class QueryExpansions(BaseModel):
    """Structured output schema for LLM-generated query expansions."""

    # Use a fixed-size tuple to generate Cerebras-compatible prefixItems schema
    model_config = {"extra": "forbid"}

    alternatives: List[str] = Field(
        min_length=_NUMBER_OF_EXPANSIONS,
        max_length=_NUMBER_OF_EXPANSIONS,
        description=(
            f"Exactly {_NUMBER_OF_EXPANSIONS} UNIQUE and DISTINCT alternative query "
            f"phrasings. Each alternative MUST be different from all others AND "
            f"different from the original query. No duplicates, no repetitions, "
            f"no variations that differ only in punctuation or capitalization."
        ),
    )


class QueryExpansion(SearchOperation):
    """Expand user query into multiple variations for better recall."""

    # Number of query expansion alternatives to generate
    NUMBER_OF_EXPANSIONS = _NUMBER_OF_EXPANSIONS

    def __init__(self, providers: List[BaseProvider]) -> None:
        """Initialize with list of LLM providers in preference order.

        Args:
            providers: List of LLM providers for structured output with fallback support
        """
        if not providers:
            raise ValueError("QueryExpansion requires at least one provider")
        self.providers = providers

    def depends_on(self) -> List[str]:
        """No dependencies - runs first if enabled."""
        return []

    async def execute(
        self,
        context: SearchContext,
        state: dict[str, Any],
        ctx: ApiContext,
    ) -> None:
        """Expand the query into variations."""
        ctx.logger.debug("[QueryExpansion] Expanding the query into variations")

        query = context.query

        # Build prompts
        system_prompt = QUERY_EXPANSION_SYSTEM_PROMPT.format(
            number_of_expansions=self.NUMBER_OF_EXPANSIONS
        )
        user_prompt = f"Original query: {query}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Get structured output from provider with fallback
        # Note: Token validation happens per-provider in the fallback loop
        async def call_provider(provider: BaseProvider) -> BaseModel:
            # Validate query length for this specific provider
            self._validate_query_length_for_provider(query, provider, ctx)
            return await provider.structured_output(messages, QueryExpansions)

        result = await self._execute_with_provider_fallback(
            providers=self.providers,
            operation_call=call_provider,
            operation_name="QueryExpansion",
            ctx=ctx,
        )

        # Validate and deduplicate alternatives
        alternatives = result.alternatives or []
        valid_alternatives = self._validate_alternatives(alternatives, query)
        ctx.logger.debug(f"[QueryExpansion] Valid alternatives: {valid_alternatives}")

        # Ensure we got exactly the expected number of alternatives
        if len(valid_alternatives) != self.NUMBER_OF_EXPANSIONS:
            raise ValueError(
                f"Query expansion failed: expected exactly {self.NUMBER_OF_EXPANSIONS} "
                f"alternatives, got {len(valid_alternatives)}. "
                f"LLM returned wrong number of valid alternatives."
            )

        # Write alternatives to state (original query remains in context.query)
        state["expanded_queries"] = valid_alternatives

        # Emit expansion done with alternatives
        await context.emitter.emit(
            "expansion_done",
            {"alternatives": valid_alternatives},
            op_name=self.__class__.__name__,
        )

    def _validate_query_length_for_provider(
        self, query: str, provider: BaseProvider, ctx: ApiContext
    ) -> None:
        """Validate query fits in specific provider's context window.

        This validates against the actual provider that will be used, not a random one.
        """
        tokenizer = getattr(provider, "llm_tokenizer", None)
        if not tokenizer:
            provider_name = provider.__class__.__name__
            raise RuntimeError(
                f"Provider {provider_name} does not have an LLM tokenizer. "
                "Cannot validate query length."
            )

        token_count = provider.count_tokens(query, tokenizer)
        ctx.logger.debug(
            f"[QueryExpansion] Token count for {provider.__class__.__name__}: {token_count}"
        )

        # Estimate prompt overhead: system prompt ~500 tokens, structured output ~500 tokens
        prompt_overhead = 1000
        max_allowed = provider.model_spec.llm_model.context_window - prompt_overhead

        if token_count > max_allowed:
            raise ValueError(
                f"Query too long for {provider.__class__.__name__}: {token_count} tokens "
                f"exceeds max of {max_allowed} for query expansion"
            )

    def _validate_alternatives(self, alternatives: List[str], original_query: str) -> List[str]:
        """Validate and clean alternatives from LLM."""
        valid = []

        for alt in alternatives:
            if not isinstance(alt, str) or not alt.strip():
                continue

            cleaned = alt.strip()

            # Skip if same as original (case-insensitive)
            if cleaned.lower() == original_query.lower():
                continue

            # Skip duplicates
            if cleaned not in valid:
                valid.append(cleaned)

        return valid
