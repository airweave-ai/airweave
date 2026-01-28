"""Schemas for the judge module."""

from typing import List, Optional

from pydantic import BaseModel, Field


class ResultSummary(BaseModel):
    """Summary of a single search result's content and relevance."""

    entity_id: str = Field(description="The entity ID of this result")
    name: str = Field(description="The name/title of the result")
    content_summary: str = Field(
        description=(
            "Brief summary of what information this entity contains. "
            "Focus on key facts, topics, or data points. 2-3 sentences max."
        )
    )
    relevance: str = Field(
        description="One sentence explaining how this result relates to the query"
    )
    useful: bool = Field(description="Whether this result is useful for answering the query")


class Judgement(BaseModel):
    """The judge's evaluation of search results."""

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

    result_summaries: List[ResultSummary] = Field(
        description="Summary of each result's relevance to the query"
    )

    useful_result_ids: List[str] = Field(
        description="Entity IDs of results that are useful for answering the query"
    )

    answer_snippet: Optional[str] = Field(
        default=None,
        description=(
            "If stopping (should_continue=False): The exact quote or key passage from the "
            "results that best answers the user's query. Copy the relevant text verbatim "
            "from the search results. Include the source document name. "
            "Leave empty if continuing to search."
        ),
    )

    advice: Optional[str] = Field(
        default=None,
        description=(
            "If continuing: Specific guidance for the planner on what to search for next. "
            "E.g., 'Try filtering to just Notion pages' or 'Search for the specific project name'. "
            "Leave empty if stopping."
        ),
    )

    error_analysis: Optional[str] = Field(
        default=None,
        description=(
            "If there was an error or zero results: Analysis of what went wrong and "
            "suggestions for fixing it. E.g., 'The filter field does not exist, "
            "try without filters.'"
        ),
    )
