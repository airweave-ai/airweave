"""Query expansion operation.

This operation expands the user's query into multiple variations
to improve recall. It can use different strategies including
LLM-based expansion or simple synonym expansion.
"""

from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from airweave.core.config import settings
from airweave.schemas.search import QueryExpansions, QueryExpansionStrategy
from airweave.search.operations.base import SearchOperation


class QueryExpansion(SearchOperation):
    """Expands a query into multiple variations.

    This operation takes the original query and generates variations
    that might match relevant documents using different terminology.
    The expanded queries are then embedded and searched in parallel.

    Example:
        Input: "customer payment issues"
        Output: ["customer payment issues", "billing problems",
                 "payment failures", "transaction errors"]
    """

    def __init__(self, strategy: str = "auto", max_expansions: int = 4):
        """Initialize query expansion operation.

        Args:
            strategy: Expansion strategy ("auto", "llm", "none")
            max_expansions: Maximum number of query variations to generate
        """
        self.strategy = strategy
        self.max_expansions = max_expansions
        self._openai_client = None

    @property
    def name(self) -> str:
        """Operation name."""
        return "query_expansion"

    @property
    def openai_client(self) -> Optional[AsyncOpenAI]:
        """Lazy-load OpenAI client.

        Returns:
            AsyncOpenAI: The OpenAI client. If OPENAI_API_KEY is not set, returns None.
        """
        if self._openai_client is None and settings.OPENAI_API_KEY:
            self._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        return self._openai_client

    async def execute(self, context: Dict[str, Any]) -> None:
        """Expand the query into multiple variations.

        Reads from context:
            - query: Original search query
            - config: SearchConfig (for strategy override)
            - logger: For logging

        Writes to context:
            - expanded_queries: List of query variations
        """
        query = context["query"]
        logger = context["logger"]
        config = context["config"]

        # Strategy can be overridden by config
        strategy = (
            config.expansion_strategy if hasattr(config, "expansion_strategy") else self.strategy
        )

        # Convert string strategy to enum if needed
        if isinstance(strategy, str):
            strategy = self._resolve_strategy(strategy)

        logger.info(f"[QueryExpansion] Expanding query using strategy: {strategy}")

        try:
            request_id = context.get("request_id")
            # Streaming path when request_id is available and LLM strategy is selected
            if request_id and strategy == QueryExpansionStrategy.LLM and self.openai_client:
                await self._stream_llm_expand(context)
            else:
                # Non-streaming or non-LLM path
                expanded_queries = await self._expand(query, strategy)

                # Limit the number of expansions
                if len(expanded_queries) > self.max_expansions:
                    expanded_queries = expanded_queries[: self.max_expansions]
                    logger.info(
                        f"[QueryExpansion] Limited expansions from {len(expanded_queries)} "
                        f"to {self.max_expansions}"
                    )

                context["expanded_queries"] = expanded_queries
                logger.info(
                    f"[QueryExpansion] Expanded query '{query[:50]}...' "
                    f"to {len(expanded_queries)} variations"
                )

                if logger.isEnabledFor(10):  # DEBUG level
                    logger.debug(f"[QueryExpansion] Variations: {expanded_queries}")

        except Exception as e:
            logger.error(f"[QueryExpansion] Failed: {e}", exc_info=True)
            # Propagate error so executor can fail the search
            emitter = context.get("emit")
            if callable(emitter):
                try:
                    await emitter(
                        "error", {"operation": self.name, "message": str(e)}, op_name=self.name
                    )
                except Exception:
                    pass
            raise

    def _resolve_strategy(self, requested: str | QueryExpansionStrategy) -> QueryExpansionStrategy:
        """Resolve the expansion strategy to use.

        Args:
            requested: The requested strategy (enum or string)

        Returns:
            QueryExpansionStrategy: The resolved strategy enum value
        """
        # Convert string to enum if needed
        if isinstance(requested, str):
            try:
                requested = QueryExpansionStrategy(requested.lower())
            except ValueError:
                # Default to AUTO for invalid values
                requested = QueryExpansionStrategy.AUTO

        # Handle AUTO strategy
        if requested == QueryExpansionStrategy.AUTO:
            if settings.OPENAI_API_KEY:
                return QueryExpansionStrategy.LLM
            return QueryExpansionStrategy.NO_EXPANSION

        return requested

    async def _expand(self, query: str, strategy: QueryExpansionStrategy) -> List[str]:
        """Main expansion entry point.

        Args:
            query: The query to expand
            strategy: The strategy to use

        Returns:
            List of queries with original first
        """
        if strategy == QueryExpansionStrategy.NO_EXPANSION:
            return [query]
        elif strategy == QueryExpansionStrategy.LLM:
            return await self._llm_expand(query)

        # Fallback
        return [query]

    async def _llm_expand(self, query: str) -> List[str]:
        """Use LLM to generate semantically similar search queries.

        Prompts GPT to create alternative phrasings that could retrieve relevant
        passages while maintaining the original search intent.

        Args:
            query: The query to expand

        Returns:
            List of queries with the original query as the first item
        """
        if not self.openai_client:
            return [query]

        try:
            # Generate alternatives using OpenAI with the same prompts used for streaming
            system_message = self._get_expansion_system_prompt()
            user_message = self._get_expansion_user_prompt(query)

            # Use structured outputs with the parse method
            completion = await self.openai_client.beta.chat.completions.parse(
                model="gpt-5-nano",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=2000,
                response_format=QueryExpansions,
            )

            parsed_result = completion.choices[0].message.parsed
            alternatives = parsed_result.alternatives if parsed_result else []

            # Process and validate the alternatives
            valid_alternatives = self._validate_alternatives(alternatives, query)

            # Build final result with original query first
            return self._build_expansion_result(query, valid_alternatives)

        except Exception:
            # Log error but don't fail the search
            return [query]

    async def _stream_llm_expand(self, context: Dict[str, Any]) -> None:  # noqa: C901
        """Stream LLM-based expansions and publish deltas.

        Emits events:
            - expansion_start { model, strategy }
            - expansion_delta { alternatives_snapshot: string[] }
            - expansion_done { alternatives: string[] }
        """
        query = context["query"]
        logger = context["logger"]

        model = "gpt-5-nano"
        emitter = context.get("emit")
        if callable(emitter):
            await emitter(
                "expansion_start",
                {"model": model, "strategy": "llm"},
                op_name=self.name,
            )

        try:
            from pydantic import BaseModel, Field

            class Step(BaseModel):
                text: str = Field(description="Concise reasoning step")

            class ExpansionResult(BaseModel):
                # IMPORTANT: steps first to stream early
                steps: List[Step] = Field(default_factory=list)
                alternatives: List[str] = Field(default_factory=list)

            async with (
                self.openai_client.beta.chat.completions.stream(  # type: ignore
                    model=model,
                    messages=[
                        {"role": "system", "content": self._get_expansion_system_prompt()},
                        {
                            "role": "user",
                            "content": (
                                self._get_expansion_user_prompt(query)
                                + "\n\nStream reasoning as a list of 'steps' FIRST, "
                                "then propose 'alternatives'."
                            ),
                        },
                    ],
                    response_format=ExpansionResult,
                ) as stream
            ):
                snapshot_alts: List[str] = []
                last_emitted_alts: List[str] = []
                last_steps_len = 0

                async for event in stream:  # type: ignore
                    if getattr(event, "type", "") == "content.delta":
                        parsed = getattr(event, "parsed", None)
                        if parsed:
                            # Normalize
                            try:
                                if isinstance(parsed, dict):
                                    parsed = ExpansionResult.model_validate(parsed)
                            except Exception:
                                continue

                            # Reasoning incremental streaming via steps FIRST
                            try:
                                if isinstance(parsed.steps, list):
                                    for i in range(last_steps_len, len(parsed.steps)):
                                        step = parsed.steps[i]
                                        text = getattr(step, "text", None) or str(step)
                                        if (
                                            isinstance(text, str)
                                            and text.strip()
                                            and callable(emitter)
                                        ):
                                            await emitter(
                                                "expansion_reason_delta",
                                                {"text": text},
                                                op_name=self.name,
                                            )
                                    last_steps_len = len(parsed.steps)
                            except Exception:
                                pass

                            # Then alternatives snapshot (dedupe emissions)
                            try:
                                if parsed.alternatives:
                                    snapshot_alts = list(dict.fromkeys(parsed.alternatives))
                                    if (
                                        callable(emitter)
                                        and snapshot_alts
                                        and snapshot_alts != last_emitted_alts
                                    ):
                                        await emitter(
                                            "expansion_delta",
                                            {"alternatives_snapshot": snapshot_alts},
                                            op_name=self.name,
                                        )
                                        last_emitted_alts = snapshot_alts[:]
                            except Exception:
                                pass

                # Final completion: always include original query first
                final_alts = ([query] + snapshot_alts) if snapshot_alts else [query]
                if len(final_alts) > self.max_expansions:
                    final_alts = final_alts[: self.max_expansions]
                context["expanded_queries"] = final_alts
                if callable(emitter):
                    await emitter("expansion_done", {"alternatives": final_alts}, op_name=self.name)
        except Exception as e:
            logger.warning(f"[QueryExpansion] Streaming failed: {e}")
            # Propagate to fail the search per policy
            raise

    async def _call_openai_for_expansion(self, query: str) -> list:
        """Call OpenAI API to generate query alternatives.

        Args:
            query: The original search query

        Returns:
            List of alternative queries from OpenAI
        """
        system_message = self._get_expansion_system_prompt()
        user_message = self._get_expansion_user_prompt(query)

        try:
            # Use structured outputs with the parse method
            completion = await self.openai_client.beta.chat.completions.parse(
                model="gpt-5-nano",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=2000,
                response_format=QueryExpansions,  # Use Pydantic model for structured output
            )

            # Extract parsed result
            parsed_result = completion.choices[0].message.parsed
            if parsed_result:
                return parsed_result.alternatives

            return []

        except Exception:
            return []

    def _get_expansion_system_prompt(self) -> str:
        """Get the system prompt for query expansion."""
        return (
            "You are a search query expansion assistant focused on finding entities. "
            "Generate up to N alternative queries that improve recall while "
            "preserving the user's intent.\n\n"
            "Core behaviors:\n"
            "- Mix (A) literal/normalized expansions that spell out constraints, and "
            "(B) semantic paraphrases.\n"
            "- For FIND/LIST/SHOW queries, include at least one literal, "
            "constraint-explicit alternative.\n"
            "- Expand abbreviations and locations: 'eng'→'engineering'/'engineer', "
            "'SF'→'San Francisco', 'NYC'→'New York City', 'NY'→'New York', "
            "'LA'→'Los Angeles'.\n"
            "- Replace vague qualifiers when helpful (e.g., 'good school'→'top universities "
            "such as Harvard, Yale, Stanford, MIT, Cambridge, Oxford').\n"
            "- Do not add constraints not implied by the query. Keep alternatives natural "
            "and non-duplicative.\n\n"
            "Examples:\n"
            "Input: eng in sf\n"
            "Alternatives (max 4):\n"
            "- people with engineering roles at companies located in San Francisco\n"
            "- engineers based in San Francisco, California\n"
            "- software engineers OR engineering managers in San Francisco\n"
            "- engineering roles in the San Francisco Bay Area\n\n"
            "Input: designers that went to a good school\n"
            "Alternatives (max 4):\n"
            "- people with current or previous role designer who attended top universities "
            "such as Harvard, Yale, Stanford, MIT, Cambridge, or Oxford\n"
            "- designers who are alumni of highly ranked universities\n"
            "- design professionals with degrees from elite universities\n"
            "- people with role designer and education at top-tier schools\n\n"
            "Streaming requirements:\n"
            "- Output a 'steps' array of concise reasoning strings FIRST to explain how you "
            "derive alternatives.\n"
            "- Then fill 'alternatives' with diverse phrasings that maintain the original intent.\n"
            "- Keep steps short and incremental so they can be streamed as they are produced."
        )

    def _get_expansion_user_prompt(self, query: str) -> str:
        """Get the user prompt for query expansion."""
        return (
            f"Original query: {query}\n\n"
            f"Instructions:\n"
            f"- Generate up to {self.max_expansions} alternatives.\n"
            f"- Include at least one literal/normalized alternative that spells out "
            f"role/company/location/education constraints if present.\n"
            f"- Expand abbreviations (e.g., 'eng'→'engineering', 'SF'→'San Francisco').\n"
            f"- When helpful, replace vague qualifiers with concrete categories (e.g., "
            f"'good school'→'top universities such as Harvard, Yale, Stanford, MIT, "
            f"Cambridge, Oxford').\n"
            f"- Avoid duplicates and keep the wording retrieval-friendly."
        )

    def _validate_alternatives(self, alternatives: list, original_query: str) -> List[str]:
        """Validate and clean the alternatives from OpenAI.

        Args:
            alternatives: Raw alternatives from OpenAI
            original_query: The original query to avoid duplicates

        Returns:
            List of valid, cleaned alternatives
        """
        valid_alternatives = []

        for alt in alternatives:
            if isinstance(alt, str) and alt.strip():
                cleaned = alt.strip()
                # Skip if it's the same as original (case-insensitive)
                if cleaned.lower() != original_query.lower():
                    valid_alternatives.append(cleaned)

        return valid_alternatives

    def _build_expansion_result(
        self, original_query: str, valid_alternatives: List[str]
    ) -> List[str]:
        """Build the final expansion result with original query first.

        Args:
            original_query: The original search query
            valid_alternatives: Validated alternatives

        Returns:
            Final list with original query first, then alternatives
        """
        result = [original_query]

        # Add alternatives up to the limit, avoiding duplicates
        for alt in valid_alternatives[: self.max_expansions]:
            if alt not in result:
                result.append(alt)

        return result
