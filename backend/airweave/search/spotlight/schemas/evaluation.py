"""Evaluation schema for spotlight search."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from .search_result_summary import SpotlightSearchResultSummary


class SpotlightEvaluation(BaseModel):
    """Spotlight evaluation schema."""

    should_continue: bool = Field(
        description=(
            "Whether to continue searching. True if results are insufficient, "
            "False if results adequately answer the query."
        )
    )

    reasoning: str = Field(
        description=(
            "Brief evaluation. Don't restate the user query or what was already tried. "
            "Focus on: what the results contain, what's missing, why continue or stop."
        )
    )

    result_summaries: list[SpotlightSearchResultSummary] = Field(
        ...,
        description="Summary of each search result. Create one summary per result, "
        "capturing what it contains and whether it's useful for the query.",
    )

    advice: Optional[str] = Field(
        default=None,
        description=(
            "Short, actionable guidance for the planner. "
            "Only suggest sources and entity types that exist in the collection metadata. "
            "Focus on what to change (filters, strategy, query terms), and what was wrong. "
            "Leave empty if stopping with sufficient results."
        ),
    )

    def to_md(self) -> str:
        """Render the evaluation as markdown for history context.

        Returns:
            Markdown string representing this evaluation.
        """
        lines = [f"**Results ({len(self.result_summaries)} found):**"]

        if self.result_summaries:
            for i, summary in enumerate(self.result_summaries, 1):
                lines.append(summary.to_md(i))
        else:
            lines.append("No results found.")

        lines.append("")
        lines.append("**Evaluator Verdict:**")
        verdict = "Continue searching" if self.should_continue else "Search complete"
        lines.append(f"- Decision: {verdict}")
        lines.append(f"- Reasoning: {self.reasoning}")

        if self.advice:
            lines.append(f"- Advice for next iteration: {self.advice}")

        return "\n".join(lines)

    @classmethod
    def render_md(cls, evaluation: Optional[SpotlightEvaluation]) -> str:
        """Render evaluation as markdown, handling None case.

        Use this instead of to_md() when the evaluation may be absent
        (e.g., direct mode skips evaluation).

        Args:
            evaluation: The evaluation, or None if unavailable.

        Returns:
            Markdown string.
        """
        if evaluation is None:
            return "*(No evaluation available.)*"
        return evaluation.to_md()
