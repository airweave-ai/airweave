"""Search planner for agentic search loop."""

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.search.agentic_search.openai import ReasoningEffort, StructuredOutputClient
from airweave.search.agentic_search.planner.collection_info import CollectionInfoBuilder
from airweave.search.agentic_search.planner.context import PLANNER_PROMPT
from airweave.search.agentic_search.planner.schemas import SearchPlan

if TYPE_CHECKING:
    from airweave.search.agentic_search.state import AgenticSearchState


class Planner:
    """Creates search plans for the agentic search loop.

    The planner uses OpenAI's reasoning models (gpt-5.2, o4-mini, etc.) to intelligently
    plan search queries. Reasoning models "think before they answer" and excel at
    complex problem-solving and multi-step planning.

    When the context window is exceeded, old iterations are automatically truncated
    from the search history to make room for new content.

    Usage:
        planner = Planner(ctx=ctx)
        plan = await planner.plan(state, db, ctx)
    """

    DEFAULT_MODEL = "gpt-5.2"
    DEFAULT_REASONING_EFFORT: ReasoningEffort = "medium"

    def __init__(
        self,
        model: str | None = None,
        reasoning_effort: ReasoningEffort | None = None,
        ctx: ApiContext | None = None,
    ) -> None:
        """Initialize the planner.

        Args:
            model: OpenAI model to use (default: gpt-5.2). Supports reasoning models
                   like o3, o4-mini, gpt-5, gpt-5.2.
            reasoning_effort: How much reasoning to use - "none", "low", "medium",
                             "high", or "xhigh". Default is "medium".
            ctx: API context for logging (passed to StructuredOutputClient)
        """
        self.client = StructuredOutputClient(
            model=model or self.DEFAULT_MODEL,
            reasoning_effort=reasoning_effort or self.DEFAULT_REASONING_EFFORT,
            ctx=ctx,
        )
        self.ctx = ctx

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
        3. Constructs the full prompt (with automatic truncation if needed)
        4. Calls the reasoning model to generate a SearchPlan
        5. Adds the plan to state
        6. Returns the plan

        Args:
            state: The agentic search state
            db: Database session for fetching collection info
            ctx: API context for logging and organization scoping

        Returns:
            SearchPlan: The generated search plan

        Raises:
            ValueError: If prompt still exceeds context after maximum truncation
            RuntimeError: If the LLM call fails
        """
        ctx.logger.debug(f"[Planner] Starting iteration {state.iteration}")

        # Step 1: Build collection info (once, on first iteration)
        if state.collection_info is None:
            ctx.logger.debug("[Planner] Building collection info...")
            state.collection_info = await self._build_collection_info(state.collection_id, db, ctx)
            ctx.logger.debug(f"[Planner] Collection info:\n{state.collection_info}")

        # Step 2 & 3: Build prompt with smart truncation
        prompt = self._build_prompt_with_truncation(state, ctx)

        # Log full prompt for debugging
        ctx.logger.debug(f"[Planner] Full prompt:\n{'=' * 80}\n{prompt}\n{'=' * 80}")

        # Step 4: Call reasoning model
        ctx.logger.debug("[Planner] Calling reasoning model for search plan...")
        plan = await self.client.structured_output(prompt, SearchPlan)

        # Step 5: Add plan to state
        state.plans[state.iteration] = plan

        # Log plan in readable format
        self._log_plan(plan, ctx)

        return plan

    def _build_prompt_with_truncation(
        self,
        state: "AgenticSearchState",
        ctx: ApiContext,
    ) -> str:
        """Build the full prompt, truncating old iterations if needed.

        Tries to fit all iterations first. If that exceeds the context window,
        progressively removes the oldest iterations until it fits.

        Args:
            state: The agentic search state
            ctx: API context for logging

        Returns:
            The prompt string that fits within context window

        Raises:
            ValueError: If even with all history removed, the prompt is too large
        """
        # Try with full history first
        search_history = self._build_search_history(state, skip_iterations=0)
        prompt = PLANNER_PROMPT.format(
            original_query=state.original_query,
            collection_info=state.collection_info,
            search_history=search_history,
        )

        fits, token_count = self.client.check_fits_context(prompt)
        if fits:
            ctx.logger.debug(f"[Planner] Prompt fits: {token_count:,} tokens")
            return prompt

        # Need to truncate - try removing oldest iterations
        ctx.logger.warning(
            f"[Planner] Prompt exceeds context ({token_count:,} > "
            f"{self.client.max_input_tokens:,}), truncating old iterations..."
        )

        # Try skipping more and more old iterations
        for skip in range(1, state.iteration + 1):
            search_history = self._build_search_history(state, skip_iterations=skip)
            prompt = PLANNER_PROMPT.format(
                original_query=state.original_query,
                collection_info=state.collection_info,
                search_history=search_history,
            )

            fits, token_count = self.client.check_fits_context(prompt)
            if fits:
                ctx.logger.warning(
                    f"[Planner] Truncated {skip} old iteration(s), now {token_count:,} tokens"
                )
                return prompt

        # Even with no history, still too large - this means collection_info is huge
        # or the base prompt is too large
        raise ValueError(
            f"Prompt exceeds context window even with no search history. "
            f"Token count: {token_count:,}, max: {self.client.max_input_tokens:,}. "
            f"Collection info may be too large."
        )

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

    def _build_search_history(
        self,
        state: "AgenticSearchState",
        skip_iterations: int = 0,
    ) -> str:
        """Build search history context from previous iterations.

        Args:
            state: The agentic search state
            skip_iterations: Number of oldest iterations to skip (for truncation)

        Returns:
            Formatted string with previous plans, YQLs, judgements, and errors
        """
        if state.is_first_iteration:
            return "(No previous iterations)"

        # Calculate which iterations to include
        start_iteration = skip_iterations
        if start_iteration >= state.iteration:
            return "(Previous iterations truncated to fit context window)"

        lines = []

        if skip_iterations > 0:
            lines.append(
                f"*Note: {skip_iterations} oldest iteration(s) truncated to fit context window*"
            )
            lines.append("")

        for i in range(start_iteration, state.iteration):
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

            # Judgement
            if i in state.judgements:
                judgement = state.judgements[i]
                lines.append("**Judge Evaluation:**")
                lines.append(str(judgement))  # TODO: Format properly once schema exists
                lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def _log_plan(self, plan: SearchPlan, ctx: ApiContext) -> None:
        """Log the search plan in a readable format.

        Args:
            plan: The generated search plan
            ctx: API context for logging
        """
        lines = [
            "",
            "=" * 60,
            "[Planner] Generated Search Plan",
            "=" * 60,
            "",
            "QUERIES:",
        ]

        for i, query in enumerate(plan.queries, 1):
            lines.append(f"  {i}. {query}")

        lines.append("")
        lines.append(f"RETRIEVAL STRATEGY: {plan.retrieval_strategy.value}")
        lines.append(f"LIMIT: {plan.limit}, OFFSET: {plan.offset}")
        lines.append("")

        if plan.filter_groups:
            lines.append(f"FILTER GROUPS ({len(plan.filter_groups)}):")
            for i, group in enumerate(plan.filter_groups, 1):
                lines.append(f"  Group {i}:")
                for cond in group.conditions:
                    lines.append(f"    - {cond.field} {cond.operator.value} {cond.value!r}")
        else:
            lines.append("FILTER GROUPS: (none)")

        lines.append("")
        lines.append("REASONING:")
        lines.append(f"  {plan.reasoning}")
        lines.append("")
        lines.append("=" * 60)

        ctx.logger.info("\n".join(lines))
