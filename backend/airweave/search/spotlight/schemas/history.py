"""Spotlight history schema.

History is created after the first full iteration completes.
It stores past iterations so the planner and evaluator can learn from previous attempts.
"""

from __future__ import annotations

from typing import Iterator

from pydantic import BaseModel, Field

from airweave.search.spotlight.external.tokenizer.interface import SpotlightTokenizerInterface

from .evaluation import SpotlightEvaluation
from .plan import SpotlightPlan

# Module-level constants for history formatting
NO_HISTORY_MESSAGE = "No search history yet. This is the first iteration."
TRUNCATION_NOTICE = "\n*(Earlier iterations truncated to fit context window)*"
HISTORY_FULLY_TRUNCATED_NOTICE = (
    "*(Search history exists but was truncated to fit context window. "
    "Previous iterations were performed but details are not shown.)*"
)


class SpotlightHistoryIteration(BaseModel):
    """A single completed search iteration stored in history.

    Created after an iteration completes (plan -> search -> evaluate).
    Contains only the fields needed for history context, not the full search results.
    """

    plan: SpotlightPlan = Field(..., description="Plan used for this iteration.")
    compiled_query: str = Field(..., description="The compiled query.")
    evaluation: SpotlightEvaluation = Field(
        ..., description="Evaluation of the results from this iteration."
    )

    def to_md(self, iteration_number: int) -> str:
        """Render this iteration as markdown for the planner prompt.

        Composes the plan.to_md() and evaluation.to_md() with iteration-specific
        context (iteration number and compiled query).

        Args:
            iteration_number: The iteration number (1-indexed for display).

        Returns:
            Markdown string representing this iteration.
        """
        lines = [
            f"### Iteration {iteration_number}",
            "",
            self.plan.to_md(),
            "",
            "**Compiled Query:**",
            f"```\n{self.compiled_query}\n```",
            "",
            self.evaluation.to_md(),
        ]

        return "\n".join(lines)


class SpotlightHistory(BaseModel):
    """History of completed search iterations.

    Stores all past iterations keyed by iteration number.
    The planner and evaluator use this to learn from previous attempts.
    """

    iterations: dict[int, SpotlightHistoryIteration] = Field(
        ...,
        description="Past iterations keyed by iteration number (1-indexed).",
    )

    @classmethod
    def get_truncation_reserve_tokens(cls, tokenizer: SpotlightTokenizerInterface) -> int:
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
    def build_history_section(
        cls,
        history: SpotlightHistory | None,
        tokenizer: SpotlightTokenizerInterface,
        budget: int,
    ) -> str:
        """Build history markdown within token budget, handling None case.

        This is the main entry point for planner/evaluator to get history markdown.
        Handles the case where history is None (first iteration).

        Args:
            history: The history object, or None if first iteration.
            tokenizer: Tokenizer for counting tokens.
            budget: Maximum tokens for history content.

        Returns:
            Markdown string with history (or NO_HISTORY_MESSAGE if None).
        """
        if history is None:
            return NO_HISTORY_MESSAGE

        return history.to_md_with_budget(tokenizer, budget)

    def iter_recent_first(self) -> Iterator[tuple[int, SpotlightHistoryIteration]]:
        """Iterate over iterations from most recent to oldest.

        Yields:
            Tuples of (iteration_number, iteration) in descending order.
        """
        for num in sorted(self.iterations.keys(), reverse=True):
            yield num, self.iterations[num]

    def add_iteration(self, iteration_number: int, iteration: SpotlightHistoryIteration) -> None:
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

    def to_md_with_budget(
        self,
        tokenizer: SpotlightTokenizerInterface,
        budget: int,
    ) -> str:
        """Build history markdown within the token budget.

        History is added from most recent to oldest until budget is exhausted.
        If truncation occurs, a notice is appended. The caller should reserve
        tokens for the truncation notice in their budget calculation using
        `SpotlightHistory.get_truncation_reserve_tokens()`.

        Args:
            tokenizer: Tokenizer for counting tokens.
            budget: Maximum tokens for history content.

        Returns:
            Markdown string with history, potentially truncated.
        """
        history_parts: list[str] = []
        tokens_used = 0

        for iter_num, iteration in self.iter_recent_first():
            iter_md = iteration.to_md(iter_num)
            iter_tokens = tokenizer.count_tokens(iter_md)

            # Check if adding this iteration would exceed budget
            if tokens_used + iter_tokens > budget:
                # Add truncation notice
                if history_parts:
                    history_parts.append(TRUNCATION_NOTICE)
                break

            history_parts.append(iter_md)
            tokens_used += iter_tokens

        # If we couldn't fit any history, indicate that
        if not history_parts:
            return HISTORY_FULLY_TRUNCATED_NOTICE

        # Join with separators (most recent first)
        return "\n\n---\n\n".join(history_parts)
