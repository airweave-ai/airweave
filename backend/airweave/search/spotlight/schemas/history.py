"""Spotlight history schema.

History is created after the first full iteration completes.
It stores past iterations so the planner can learn from previous attempts.
"""

from typing import Iterator

from pydantic import BaseModel, Field

from .evaluation import SpotlightEvaluation
from .plan import SpotlightPlan


class SpotlightIteration(BaseModel):
    """A single completed search iteration.

    Stored in history after the iteration completes (plan -> search -> evaluate).
    """

    plan: SpotlightPlan = Field(..., description="Plan used for this iteration.")
    compiled_query: str = Field(..., description="The compiled query.")
    evaluation: SpotlightEvaluation = Field(
        ..., description="Evaluation of the results used for this iteration."
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
    The planner uses this to learn from previous attempts.
    """

    iterations: dict[int, SpotlightIteration] = Field(
        ...,
        description="Past iterations keyed by iteration number (1-indexed).",
    )

    def to_md_empty(self) -> str:
        """Return markdown indicating no history exists yet.

        Used by the planner when this is the first iteration.
        """
        return "No search history yet. This is the first iteration."

    def iter_recent_first(self) -> Iterator[tuple[int, SpotlightIteration]]:
        """Iterate over iterations from most recent to oldest.

        Yields:
            Tuples of (iteration_number, iteration) in descending order.
        """
        for num in sorted(self.iterations.keys(), reverse=True):
            yield num, self.iterations[num]

    def add_iteration(self, iteration_number: int, iteration: SpotlightIteration) -> None:
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

    @property
    def latest_iteration_number(self) -> int:
        """Get the most recent iteration number.

        Returns:
            The highest iteration number in history.

        Raises:
            ValueError: If history is empty (should not happen in normal use).
        """
        if not self.iterations:
            raise ValueError("History is empty - no iterations yet.")
        return max(self.iterations.keys())
