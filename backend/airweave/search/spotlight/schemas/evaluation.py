"""Evaluation schema for spotlight search."""

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
            "Explain your evaluation: Why are the results sufficient or insufficient? "
            "What aspects of the query are covered or missing?"
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
            "Guidance for the planner on what to do next. "
            "If continuing: suggest what to search for "
            "(e.g., 'Try filtering to just Notion pages'). "
            "If errors or zero results: analyze what went wrong and how to fix it. "
            "E.g., 'The filter field does not exist, try without filters'."
            "Leave empty if stopping with sufficient results."
        ),
    )
