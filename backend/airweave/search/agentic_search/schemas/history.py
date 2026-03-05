"""AgenticSearch history schema.

History is created after the first full iteration completes.
It stores past iterations so the planner can learn from previous attempts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Optional

from pydantic import BaseModel, Field

from airweave.search.agentic_search.external.tokenizer.interface import (
    AgenticSearchTokenizerInterface,
)

from .evaluation import AgenticSearchEvaluation
from .plan import AgenticSearchPlan
from .search_result import ResultBrief

# Module-level constants for history formatting
NO_HISTORY_MESSAGE = "No search history yet. This is the first iteration."
TRUNCATION_NOTICE = "\n*(Earlier iterations truncated to fit context window)*"
HISTORY_FULLY_TRUNCATED_NOTICE = (
    "*(Search history exists but was truncated to fit context window. "
    "Previous iterations were performed but details are not shown.)*"
)

# Maximum length for query text in the strategy ledger (characters)
_LEDGER_QUERY_MAX_LEN = 60


@dataclass
class HistorySectionInfo:
    """Information about the rendered history section.

    Returned by render_md so callers (planner) know exactly
    how many detailed iterations fit vs how many were truncated.
    Note: the strategy ledger always shows ALL iterations regardless.
    """

    markdown: str
    iterations_shown: int
    iterations_total: int


class AgenticSearchHistoryIteration(BaseModel):
    """A single completed search iteration stored in history.

    Created after an iteration completes (plan -> search -> evaluate).
    Contains the plan, a deterministic result brief, and the evaluation.
    """

    plan: AgenticSearchPlan = Field(..., description="Plan used for this iteration.")
    result_brief: ResultBrief = Field(..., description="Deterministic summary of what was found.")
    evaluation: AgenticSearchEvaluation = Field(
        ..., description="Evaluation of the results from this iteration."
    )
    evaluator_results_shown: Optional[int] = Field(
        default=None,
        description="How many results the evaluator actually saw (may be fewer than total due to "
        "context window limits). None for fast mode (no evaluator).",
    )
    search_error: Optional[str] = Field(
        default=None,
        description="Error message if the search query failed this iteration.",
    )

    def to_md(self, iteration_number: int) -> str:
        """Render this iteration as markdown for the planner prompt.

        Composes the plan.to_md(), result_brief.to_md(), and evaluation.to_md().

        Args:
            iteration_number: The iteration number (1-indexed for display).

        Returns:
            Markdown string representing this iteration.
        """
        # Build result brief with evaluator visibility info
        result_brief_md = self.result_brief.to_md()
        if (
            self.evaluator_results_shown is not None
            and self.evaluator_results_shown < self.result_brief.total_count
        ):
            result_brief_md += (
                f"\n⚠ Evaluator only saw {self.evaluator_results_shown}/"
                f"{self.result_brief.total_count} results (rest did not fit in context)."
            )

        # Add search error warning if the query failed
        error_md = ""
        if self.search_error:
            error_md = (
                f"\n⚠ **SEARCH ERROR:** {self.search_error} — "
                f"The 0 results are from a failed query, not an empty result set.\n"
            )

        lines = [
            f"### Iteration {iteration_number}",
            "",
            self.plan.to_md(),
            error_md,
            result_brief_md,
            "",
            self.evaluation.to_md(),
        ]

        return "\n".join(lines)

    def to_ledger_line(self, iteration_number: int) -> str:
        """Render a compact one-line summary for the strategy ledger.

        Captures strategy, query, filter scope, result count, and decision so the
        planner can see at a glance what has already been tried.

        Args:
            iteration_number: The iteration number (1-indexed for display).

        Returns:
            A single markdown list item summarising this iteration.
        """
        plan = self.plan
        query = plan.query.primary
        if len(query) > _LEDGER_QUERY_MAX_LEN:
            query = query[: _LEDGER_QUERY_MAX_LEN - 1] + "…"

        strategy = plan.retrieval_strategy.value
        n_results = self.result_brief.total_count
        decision = "continued" if self.evaluation.should_continue else "stopped"

        # Compact filter summary
        if plan.filter_groups:
            filter_parts: list[str] = []
            for fg in plan.filter_groups:
                conds = [f"{c.field.value} {c.operator.value} {c.value!r}" for c in fg.conditions]
                filter_parts.append(" & ".join(conds))
            filter_summary = " OR ".join(filter_parts)
        else:
            filter_summary = "no filters"

        limit = plan.limit

        return (
            f"- **{iteration_number}**: {strategy} `{query}` "
            f"[{filter_summary}] → {n_results}/{limit} results, {decision}"
        )


class AgenticSearchHistory(BaseModel):
    """History of completed search iterations.

    Stores all past iterations keyed by iteration number.
    The planner uses this to learn from previous attempts.
    """

    iterations: dict[int, AgenticSearchHistoryIteration] = Field(
        ...,
        description="Past iterations keyed by iteration number (1-indexed).",
    )

    @classmethod
    def get_truncation_reserve_tokens(cls, tokenizer: AgenticSearchTokenizerInterface) -> int:
        """Get the maximum tokens needed for truncation notices.

        Use this when calculating budget to ensure truncation notices always fit.

        Args:
            tokenizer: Tokenizer for counting tokens.

        Returns:
            Maximum tokens needed for either truncation notice.
        """
        return max(
            tokenizer.count_tokens(TRUNCATION_NOTICE),
            tokenizer.count_tokens(HISTORY_FULLY_TRUNCATED_NOTICE),
        )

    @classmethod
    def render_md(
        cls,
        history: AgenticSearchHistory | None,
        tokenizer: AgenticSearchTokenizerInterface,
        budget: int,
    ) -> HistorySectionInfo:
        """Render history as markdown within token budget, handling None case.

        This is the main entry point for the planner/composer to get history
        markdown. Handles the case where history is None (first iteration).

        Args:
            history: The history object, or None if first iteration.
            tokenizer: Tokenizer for counting tokens.
            budget: Maximum tokens for history content.

        Returns:
            HistorySectionInfo with markdown, iterations_shown, and iterations_total.
        """
        if history is None:
            return HistorySectionInfo(
                markdown=NO_HISTORY_MESSAGE,
                iterations_shown=0,
                iterations_total=0,
            )

        return history.to_md_with_budget(tokenizer, budget)

    def iter_recent_first(self) -> Iterator[tuple[int, AgenticSearchHistoryIteration]]:
        """Iterate over iterations from most recent to oldest.

        Yields:
            Tuples of (iteration_number, iteration) in descending order.
        """
        for num in sorted(self.iterations.keys(), reverse=True):
            yield num, self.iterations[num]

    def add_iteration(
        self, iteration_number: int, iteration: AgenticSearchHistoryIteration
    ) -> None:
        """Add a completed iteration to history.

        Iterations must be added sequentially. The first iteration must be 1,
        and each subsequent iteration must be exactly one more than the latest.

        Args:
            iteration_number: The iteration number (1-indexed).
            iteration: The completed iteration to add.

        Raises:
            ValueError: If iteration_number is not the next expected number.
        """
        expected = (max(self.iterations.keys()) + 1) if self.iterations else 1
        if iteration_number != expected:
            raise ValueError(
                f"Expected iteration {expected}, got {iteration_number}. "
                "Iterations must be added sequentially."
            )
        self.iterations[iteration_number] = iteration

    def build_strategy_ledger(self) -> str:
        """Build a compact strategy ledger covering all past iterations.

        The ledger gives the planner and evaluator a quick overview of every
        strategy already tried (query, retrieval strategy, filters, result count,
        decision) so they can avoid repeating previous approaches. Each iteration
        is one line.

        Returns:
            Markdown string with the strategy ledger.
        """
        lines = ["### Strategy Ledger", ""]
        for iter_num in sorted(self.iterations.keys()):
            lines.append(self.iterations[iter_num].to_ledger_line(iter_num))
        return "\n".join(lines)

    def to_md_with_budget(
        self,
        tokenizer: AgenticSearchTokenizerInterface,
        budget: int,
    ) -> HistorySectionInfo:
        """Build history markdown within the token budget.

        Renders two sections:
        1. **Strategy ledger** — a compact one-line-per-iteration summary that is
           always included in full. This ensures the planner can see all past
           strategies even when detailed iterations are truncated.
        2. **Detailed iterations** — iteration details added from most recent to
           oldest until the remaining budget is exhausted.

        The caller should reserve tokens for the truncation notice in their budget
        calculation using ``AgenticSearchHistory.get_truncation_reserve_tokens()``.

        Args:
            tokenizer: Tokenizer for counting tokens.
            budget: Maximum tokens for history content.

        Returns:
            HistorySectionInfo with markdown, iterations_shown, and iterations_total.
        """
        total_iterations = len(self.iterations)

        # Always include the strategy ledger
        ledger_md = self.build_strategy_ledger()
        ledger_tokens = tokenizer.count_tokens(ledger_md)

        # If the ledger alone exceeds the budget, return just the ledger (it's the
        # highest-value content for preventing repetition)
        if ledger_tokens >= budget:
            return HistorySectionInfo(
                markdown=ledger_md,
                iterations_shown=0,
                iterations_total=total_iterations,
            )

        remaining_budget = budget - ledger_tokens

        # Build detailed iterations with remaining budget (most recent first)
        detail_parts: list[str] = []
        iterations_shown = 0
        tokens_used = 0

        for iter_num, iteration in self.iter_recent_first():
            iter_md = iteration.to_md(iter_num)
            iter_tokens = tokenizer.count_tokens(iter_md)

            # Check if adding this iteration would exceed budget
            if tokens_used + iter_tokens > remaining_budget:
                # Add truncation notice
                if detail_parts:
                    detail_parts.append(TRUNCATION_NOTICE)
                break

            detail_parts.append(iter_md)
            iterations_shown += 1
            tokens_used += iter_tokens

        # Combine ledger + detailed iterations
        if detail_parts:
            details_md = "\n\n---\n\n".join(detail_parts)
            markdown = f"{ledger_md}\n\n---\n\n### Detailed Iterations\n\n{details_md}"
        else:
            # Ledger only (no room for any detailed iteration)
            markdown = ledger_md

        return HistorySectionInfo(
            markdown=markdown,
            iterations_shown=iterations_shown,
            iterations_total=total_iterations,
        )
