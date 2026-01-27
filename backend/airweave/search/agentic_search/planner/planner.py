"""Search planner for agentic search loop."""

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.search.agentic_search.planner.context import PLANNER_PROMPT
from airweave.search.agentic_search.planner.schemas import SearchPlan
from airweave.search.agentic_search.utils.collection_info import CollectionInfoBuilder
from airweave.search.providers._base import BaseProvider

if TYPE_CHECKING:
    from airweave.search.agentic_search.state import AgenticSearchState


class Planner:
    """Creates search plans for the agentic search loop.

    The planner is responsible for:
    1. Building collection info (on first iteration)
    2. Building search history context from previous iterations
    3. Calling the LLM to generate a search plan
    4. Adding the plan to the state

    Usage:
        planner = Planner(providers=[openai_provider, groq_provider])
        plan = await planner.plan(state, db, ctx)
    """

    def __init__(self, providers: list[BaseProvider]) -> None:
        """Initialize the planner.

        Args:
            providers: List of LLM providers in preference order for fallback support
        """
        if not providers:
            raise ValueError("Planner requires at least one provider")
        self.providers = providers

    async def plan(
        self,
        state: "AgenticSearchState",
        db: AsyncSession,
        ctx: ApiContext,
    ) -> SearchPlan:
        """Create a search plan based on the current state.

        This method:
        1. Builds collection info if not already present (first iteration)
        2. Builds search history context from previous iterations
        3. Constructs the full prompt
        4. Calls the LLM to generate a SearchPlan
        5. Adds the plan to state
        6. Returns the plan

        Args:
            state: The agentic search state
            db: Database session for fetching collection info
            ctx: API context for logging and organization scoping

        Returns:
            SearchPlan: The generated search plan

        Raises:
            CollectionInfoError: If collection info cannot be built
            RuntimeError: If all LLM providers fail
        """
        ctx.logger.debug(f"[Planner] Starting iteration {state.iteration}")

        # Step 1: Build collection info (once, on first iteration)
        if state.collection_info is None:
            ctx.logger.debug("[Planner] Building collection info...")
            state.collection_info = await self._build_collection_info(state.collection_id, db, ctx)

        # Step 2: Build search history from previous iterations
        search_history = self._build_search_history(state)

        # Step 3: Build the full prompt
        prompt = PLANNER_PROMPT.format(
            original_query=state.original_query,
            collection_info=state.collection_info,
            search_history=search_history,
        )

        # Step 4: Call LLM to generate plan
        ctx.logger.debug("[Planner] Calling LLM for search plan...")
        plan = await self._call_llm(prompt, ctx)

        # Step 5: Add plan to state
        state.plans[state.iteration] = plan

        ctx.logger.debug(
            f"[Planner] Generated plan with {len(plan.queries)} queries, "
            f"{len(plan.filter_groups)} filter groups, "
            f"strategy={plan.retrieval_strategy.value}"
        )

        return plan

    async def _build_collection_info(
        self,
        collection_id: str,
        db: AsyncSession,
        ctx: ApiContext,
    ) -> str:
        """Build collection info markdown using CollectionInfoBuilder.

        Args:
            collection_id: The collection's readable ID
            db: Database session
            ctx: API context

        Returns:
            Markdown string with collection sources, entity types, and fields
        """
        builder = CollectionInfoBuilder(db, ctx)
        return await builder.build_markdown(collection_id)

    def _build_search_history(self, state: "AgenticSearchState") -> str:
        """Build search history context from previous iterations.

        Args:
            state: The agentic search state

        Returns:
            Formatted string with previous plans, YQLs, results, judgements, and errors
        """
        if state.is_first_iteration:
            return "(No previous iterations)"

        lines = []

        for i in range(state.iteration):
            lines.append(f"### Iteration {i + 1}")
            lines.append("")

            # Plan
            if i in state.plans:
                plan = state.plans[i]
                lines.append("**Plan:**")
                lines.append(f"- Queries: {plan.queries}")
                lines.append(f"- Filter groups: {len(plan.filter_groups)}")
                lines.append(f"- Strategy: {plan.retrieval_strategy.value}")
                lines.append(f"- Limit: {plan.limit}, Offset: {plan.offset}")
                lines.append(f"- Reasoning: {plan.reasoning}")
                lines.append("")

            # YQL
            if i in state.yqls:
                lines.append("**YQL Query:**")
                lines.append(f"```yql\n{state.yqls[i]}\n```")
                lines.append("")

            # Error (if any)
            if i in state.errors:
                lines.append("**Error:**")
                lines.append(f"```\n{state.errors[i]}\n```")
                lines.append("")

            # Results summary
            if i in state.results:
                results = state.results[i]
                lines.append(f"**Results:** {len(results)} documents returned")
                # TODO: Add brief summary of top results?
                lines.append("")

            # Judgement
            if i in state.judgements:
                judgement = state.judgements[i]
                lines.append("**Judge Evaluation:**")
                lines.append(str(judgement))  # TODO: Format properly once schema exists
                lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    async def _call_llm(self, prompt: str, ctx: ApiContext) -> SearchPlan:
        """Call LLM with provider fallback to generate a SearchPlan.

        Args:
            prompt: The full prompt string
            ctx: API context for logging

        Returns:
            SearchPlan from the LLM

        Raises:
            RuntimeError: If all providers fail
        """
        messages = [
            {"role": "user", "content": prompt},
        ]

        last_error = None
        for i, provider in enumerate(self.providers):
            try:
                ctx.logger.debug(
                    f"[Planner] Trying provider {provider.__class__.__name__} "
                    f"({i + 1}/{len(self.providers)})"
                )
                plan = await provider.structured_output(messages, SearchPlan)
                ctx.logger.debug(
                    f"[Planner] Successfully got plan from {provider.__class__.__name__}"
                )
                return plan
            except Exception as e:
                last_error = e
                if BaseProvider.is_retryable_error(e) and i < len(self.providers) - 1:
                    ctx.logger.warning(
                        f"[Planner] Provider {provider.__class__.__name__} failed "
                        f"with retryable error: {e}. Trying next provider..."
                    )
                    continue
                else:
                    raise

        raise RuntimeError(
            f"All {len(self.providers)} providers failed for Planner. Last error: {last_error}"
        )
