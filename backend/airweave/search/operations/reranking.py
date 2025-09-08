"""LLM-based reranking operation.

This module contains the LLM reranking operation that uses OpenAI
to reorder search results based on relevance to the original query.
"""

from typing import Any, Dict, List, Optional

from airweave.search.operations.base import SearchOperation


class LLMReranking(SearchOperation):
    """Rerank search results using LLM.

    This operation sends the search results and the original query to
    OpenAI and asks the LLM to rerank the results to ensure the most
    relevant results appear at the top.
    """

    def __init__(self, model: str = "gpt-5-nano", max_candidates: int = 100):
        """Initialize LLM reranking.

        Args:
            model: OpenAI model to use for reranking
            max_candidates: Maximum number of top results to consider for LLM reranking
        """
        self.model = model
        self.max_candidates = max(1, int(max_candidates))

    @property
    def name(self) -> str:
        """Operation name."""
        return "llm_reranking"

    @property
    def depends_on(self) -> List[str]:
        """Reranking depends on vector search."""
        return ["vector_search"]

    async def execute(self, context: Dict[str, Any]) -> None:  # noqa: C901
        """Execute LLM-based reranking.

        Reads from context:
            - raw_results: Initial search results
            - query: Original search query
            - config: SearchConfig
            - logger: For logging
            - openai_api_key: API key for OpenAI

        Writes to context:
            - final_results: Reranked and limited results
        """
        from openai import AsyncOpenAI
        from pydantic import BaseModel, Field

        results = context.get("raw_results", [])
        query = context["query"]
        config = context["config"]
        logger = context["logger"]
        openai_api_key = context.get("openai_api_key")

        if not results:
            context["final_results"] = []
            logger.info(f"[{self.name}] No results to rerank")
            return

        if not openai_api_key:
            # If no API key, just use original results
            context["final_results"] = results[: config.limit]
            logger.warning(f"[{self.name}] No OpenAI API key, using original order")
            return

        logger.info(f"[{self.name}] Reranking {len(results)} results using LLM")

        try:
            # Prepare results for LLM with indices
            k = min(len(results), self.max_candidates)
            results_for_llm = []
            for i, result in enumerate(results[:k]):
                payload = result.get("payload", {})
                content = (
                    payload.get("md_content")
                    or payload.get("content")
                    or payload.get("text", "")
                    or payload.get("embeddable_text", "")
                )

                results_for_llm.append(
                    {
                        "index": i,
                        "source": payload.get("source_name", "Unknown"),
                        "title": payload.get("title", "Untitled"),
                        "content": content,
                        "score": result.get("score", 0),
                    }
                )

            # Define structured output for reranking
            class Step(BaseModel):
                text: str

            class RankedResult(BaseModel):
                index: int = Field(description="Original index of the result")
                relevance_score: float = Field(
                    ge=0.0, le=1.0, description="Relevance score from 0 to 1"
                )
                reasoning: str = Field(description="Brief explanation for the ranking")

            class RerankedResults(BaseModel):
                # IMPORTANT: steps first to stream early
                steps: List[Step] = Field(default_factory=list)
                rankings: List[RankedResult] = Field(
                    description="Results ordered by relevance, most relevant first"
                )

            # Create OpenAI client
            client = AsyncOpenAI(api_key=openai_api_key)

            # Create prompt
            system_prompt = (
                "You are a search result reranking expert. Your task is to reorder search "
                "results based on their relevance to the user's query.\n\n"
                "Use the vector similarity score as one helpful signal, but do not rely on it "
                "exclusively.\n"
                "- Prioritize direct topical relevance to the user's query\n"
                "- Prefer higher quality, complete, and specific information over vague or "
                "boilerplate text\n"
                "- Consider source reliability and authoritativeness\n"
                "- When items are equally relevant, the higher vector score should break ties\n\n"
                "Only rerank when it improves relevance. If the initial order already reflects "
                "the best results, keep the order unchanged.\n\n"
                "Streaming requirements:\n"
                "- First, emit a 'steps' array of concise reasoning strings explaining how "
                "you assess relevance.\n"
                "- Then, emit 'rankings' as a list of objects with index and relevance_score.\n"
                "- Keep steps short and incremental so they can be "
                "streamed as they are produced.\n\n"
                "Return results ordered from most to least relevant."
            )

            user_prompt = f"""Query: {query}

Search Results:
{self._format_results_for_prompt(results_for_llm)}

Please rerank these results from most to least relevant to the query."""

            request_id: Optional[str] = context.get("request_id")

            if request_id:
                # Streaming path
                emitter = context.get("emit")
                if callable(emitter):
                    await emitter(
                        "reranking_start",
                        {"model": self.model, "strategy": "llm", "k": len(results_for_llm)},
                        op_name=self.name,
                    )

                rankings_snapshot: List[Dict[str, Any]] = []
                last_emitted_snapshot: List[Dict[str, Any]] = []
                last_steps_len = 0
                async with client.beta.chat.completions.stream(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format=RerankedResults,
                ) as stream:
                    async for event in stream:
                        if getattr(event, "type", "") == "content.delta":
                            parsed = getattr(event, "parsed", None)
                            if parsed:
                                # Normalize dict to Pydantic model
                                try:
                                    if isinstance(parsed, dict):
                                        parsed = RerankedResults.model_validate(parsed)
                                except Exception:
                                    continue

                                # Reasoning FIRST via steps array
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
                                                    "reranking_reason_delta",
                                                    {"text": text},
                                                    op_name=self.name,
                                                )
                                        last_steps_len = len(parsed.steps)
                                except Exception:
                                    pass

                                # Then rankings snapshot
                                if getattr(parsed, "rankings", None):
                                    rankings_snapshot = [
                                        {
                                            "index": r.index,
                                            "relevance_score": r.relevance_score,
                                        }
                                        for r in parsed.rankings
                                    ]
                                    if (
                                        callable(emitter)
                                        and rankings_snapshot != last_emitted_snapshot
                                    ):
                                        await emitter(
                                            "reranking_delta",
                                            {"rankings_snapshot": rankings_snapshot},
                                            op_name=self.name,
                                        )
                                        last_emitted_snapshot = [*rankings_snapshot]

                # Apply final order
                final_results: List[Dict[str, Any]] = []
                ranked_indices = set()
                for item in rankings_snapshot:
                    idx = item.get("index", -1)
                    if isinstance(idx, int) and 0 <= idx < len(results):
                        final_results.append(results[idx])
                        ranked_indices.add(idx)
                # Fill remaining
                for i, result in enumerate(results):
                    if i not in ranked_indices and len(final_results) < config.limit:
                        final_results.append(result)

                context["final_results"] = final_results[: config.limit]
                if callable(emitter):
                    await emitter(
                        "reranking_done",
                        {"rankings": rankings_snapshot, "applied": True},
                        op_name=self.name,
                    )
                logger.info(f"[{self.name}] Reranking stream complete")
            else:
                # Non-streaming path
                response = await client.beta.chat.completions.parse(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format=RerankedResults,
                )

                if response.choices[0].message.parsed:
                    reranked = response.choices[0].message.parsed

                    # Reorder results based on LLM ranking
                    final_results = []
                    for ranked_item in reranked.rankings:
                        if ranked_item.index < len(results):
                            final_results.append(results[ranked_item.index])
                            logger.debug(
                                f"[{self.name}] Ranked position {len(final_results)}: "
                                f"index={ranked_item.index}, "
                                f"score={ranked_item.relevance_score:.2f}, "
                                f"reason={ranked_item.reasoning[:50]}..."
                            )

                    # Add any remaining results that weren't ranked
                    ranked_indices = {r.index for r in reranked.rankings}
                    for i, result in enumerate(results):
                        if i not in ranked_indices and len(final_results) < config.limit:
                            final_results.append(result)

                    context["final_results"] = final_results[: config.limit]
                    logger.info(
                        f"[{self.name}] Successfully reranked to "
                        f"{len(context['final_results'])} results"
                    )
                else:
                    # Fallback to original order
                    context["final_results"] = results[: config.limit]
                    logger.warning(f"[{self.name}] No reranking received, using original order")

        except Exception as e:
            logger.error(f"[{self.name}] Failed: {e}", exc_info=True)
            # Propagate to fail the search per policy
            raise

    def _format_results_for_prompt(self, results: List[Dict]) -> str:
        """Format results for the LLM prompt.

        Args:
            results: List of result dictionaries with index, source, title, content

        Returns:
            Formatted string for the prompt
        """
        formatted = []
        for r in results:
            formatted.append(
                f"[{r['index']}] Source: {r['source']}, Title: {r['title']}\n"
                f"Content: {r['content']}\n"
                f"Original Score: {r['score']:.3f}"
            )
        return "\n\n".join(formatted)
