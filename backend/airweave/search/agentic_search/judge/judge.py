"""Search judge for agentic search loop."""

from typing import TYPE_CHECKING

from airweave.api.context import ApiContext
from airweave.search.agentic_search.context import (
    AIRWEAVE_BACKGROUND,
    ResultsFormatter,
    SearchHistoryBuilder,
)
from airweave.search.agentic_search.judge.schemas import Judgement
from airweave.search.agentic_search.judge.task import JUDGE_TASK
from airweave.search.agentic_search.openai import ReasoningEffort, StructuredOutputClient

if TYPE_CHECKING:
    from airweave.search.agentic_search.state import AgenticSearchState


class Judge:
    """Evaluates search results and decides whether to continue searching.

    The judge uses OpenAI's reasoning models to evaluate search results and determine
    if they adequately answer the user's query. It provides feedback to guide the
    planner in subsequent iterations.

    Usage:
        judge = Judge(ctx=ctx)
        judgement = await judge.judge(state, ctx)
    """

    DEFAULT_MODEL = "gpt-5.2"
    DEFAULT_REASONING_EFFORT: ReasoningEffort = "medium"

    def __init__(
        self,
        model: str | None = None,
        reasoning_effort: ReasoningEffort | None = None,
        ctx: ApiContext | None = None,
    ) -> None:
        """Initialize the judge.

        Args:
            model: OpenAI model to use (default: gpt-5.2). Supports reasoning models.
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

    async def judge(
        self,
        state: "AgenticSearchState",
        ctx: ApiContext,
    ) -> Judgement:
        """Evaluate search results and decide whether to continue.

        Args:
            state: The agentic search state with current results
            ctx: API context for logging

        Returns:
            Judgement with decision, reasoning, and advice
        """
        ctx.logger.debug(f"[Judge] Evaluating results for iteration {state.iteration}")

        # Build the prompt
        prompt = self._build_prompt(state, ctx)

        # Log full prompt for debugging
        ctx.logger.debug(f"[Judge] Full prompt:\n{'=' * 80}\n{prompt}\n{'=' * 80}")

        # Call reasoning model
        ctx.logger.debug("[Judge] Calling reasoning model for judgement...")
        judgement = await self.client.structured_output(prompt, Judgement)

        # Store judgement in state
        state.judgements[state.iteration] = judgement

        # Log judgement
        self._log_judgement(judgement, ctx)

        return judgement

    def _build_prompt(
        self,
        state: "AgenticSearchState",
        ctx: ApiContext,
    ) -> str:
        """Build the full judge prompt.

        Args:
            state: The agentic search state
            ctx: API context for logging

        Returns:
            Complete prompt string for the judge LLM
        """
        # Get current iteration data
        current_plan = state.plans.get(state.iteration)
        current_vespa_query = state.vespa_queries.get(state.iteration)
        current_results = state.results.get(state.iteration, [])
        current_error = state.errors.get(state.iteration)

        # Format current plan
        plan_md = self._format_plan(current_plan) if current_plan else "(No plan)"

        # Format VespaQuery
        vespa_query_md = (
            self._format_vespa_query(current_vespa_query)
            if current_vespa_query
            else "(No query executed)"
        )

        # Format results
        results_md = ResultsFormatter.format_results_markdown(current_results)

        # Format error
        error_md = f"```\n{current_error}\n```" if current_error else "(No error)"

        # Format search history (excluding current iteration)
        history_builder = SearchHistoryBuilder(state)
        # Get history of iterations BEFORE current one
        if state.iteration > 0:
            # Temporarily decrement iteration to get history without current
            original_iteration = state.iteration
            state.iteration = original_iteration
            history_md = history_builder.format_history_markdown(
                include_vespa_queries=True,
                include_judgements=True,
            )
            # Filter out current iteration from history (it's shown separately)
            # The history builder uses state.iteration as the upper bound
        else:
            history_md = "(No previous iterations)"

        # Build full prompt
        return f"""# Airweave Background

{AIRWEAVE_BACKGROUND}

---

{JUDGE_TASK}

---

# Collection Information

{state.collection_info or "(Collection info not available)"}

---

# Original User Query

{state.original_query}

---

# Current Iteration ({state.iteration + 1})

## Plan Used

{plan_md}

## Vespa Query Executed

{vespa_query_md}

## Results

{results_md}

## Error (if any)

{error_md}

---

# Search History

{history_md}
"""

    def _format_plan(self, plan) -> str:
        """Format a SearchPlan as markdown."""
        lines = [
            f"- **Queries:** {plan.queries}",
            f"- **Strategy:** {plan.retrieval_strategy.value}",
            f"- **Limit:** {plan.limit}, **Offset:** {plan.offset}",
        ]

        if plan.filter_groups:
            lines.append(f"- **Filter groups:** {len(plan.filter_groups)}")
            for i, group in enumerate(plan.filter_groups, 1):
                conditions_str = ", ".join(
                    f"{c.field} {c.operator.value} {c.value!r}" for c in group.conditions
                )
                lines.append(f"  - Group {i}: {conditions_str}")

        lines.append(f"- **Reasoning:** {plan.reasoning}")

        return "\n".join(lines)

    def _format_vespa_query(self, vespa_query) -> str:
        """Format a VespaQuery as markdown."""
        lines = [
            "```yql",
            vespa_query.yql,
            "```",
            "",
            "**Params:**",
            "```",
            vespa_query.format_params_for_logging(),
            "```",
        ]
        return "\n".join(lines)

    def _log_judgement(self, judgement: Judgement, ctx: ApiContext) -> None:
        """Log the judgement in a readable format."""
        lines = [
            "",
            "=" * 60,
            "[Judge] Judgement",
            "=" * 60,
            "",
            f"SHOULD CONTINUE: {judgement.should_continue}",
            "",
            "REASONING:",
            f"  {judgement.reasoning}",
            "",
            f"USEFUL RESULTS: {len(judgement.useful_result_ids)} / "
            f"{len(judgement.result_summaries)}",
        ]

        if judgement.useful_result_ids:
            lines.append(f"  IDs: {judgement.useful_result_ids}")

        if judgement.advice:
            lines.append("")
            lines.append("ADVICE:")
            lines.append(f"  {judgement.advice}")

        if judgement.error_analysis:
            lines.append("")
            lines.append("ERROR ANALYSIS:")
            lines.append(f"  {judgement.error_analysis}")

        lines.append("")
        lines.append("=" * 60)

        ctx.logger.info("\n".join(lines))
