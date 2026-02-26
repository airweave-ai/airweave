"""Evaluation schema for agentic search."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class AgenticSearchEvaluation(BaseModel):
    """AgenticSearch evaluation schema.

    Field order matters — the model generates JSON fields sequentially.
    By placing reasoning before should_continue, the model is forced to
    think through its assessment before deciding whether to continue.
    This prevents premature stopping based on topical pattern-matching.
    """

    reasoning: str = Field(
        description=(
            "Your assessment as natural inner monologue — think out loud. "
            "Reference specific results by name: what they contain and what's missing. "
            "Focus on: do the results DIRECTLY ANSWER the question (not just relate to the "
            "topic), what's missing, and whether to continue or stop."
        )
    )

    should_continue: bool = Field(
        description=(
            "Whether to continue searching. Set this AFTER writing your reasoning. "
            "True if no result directly answers the query. "
            "False ONLY if you can point to a specific passage that answers the question, "
            "OR if the search space is exhausted."
        )
    )

    answer_found: bool = Field(
        description=(
            "Whether the current results directly answer the user's query. "
            "True if you can point to a specific passage that answers the question. "
            "False if results are only tangentially related, or if the search is exhausted "
            "without finding a direct answer. This field is used to determine whether "
            "a final consolidation search is needed."
        )
    )

    def to_md(self) -> str:
        """Render the evaluation as markdown for history context.

        Returns:
            Markdown string representing this evaluation.
        """
        lines = [
            "**Reasoning:**",
            self.reasoning,
        ]

        verdict = "Continue searching" if self.should_continue else "Search complete"
        answer_status = "Yes" if self.answer_found else "No"
        lines.append(f"\n**Decision:** {verdict}")
        lines.append(f"**Answer found:** {answer_status}")

        return "\n".join(lines)

    @classmethod
    def render_md(cls, evaluation: Optional[AgenticSearchEvaluation]) -> str:
        """Render evaluation as markdown, handling None case.

        Use this instead of to_md() when the evaluation may be absent
        (e.g., fast mode skips evaluation).

        Args:
            evaluation: The evaluation, or None if unavailable.

        Returns:
            Markdown string.
        """
        if evaluation is None:
            return "*(No evaluation available.)*"
        return evaluation.to_md()
