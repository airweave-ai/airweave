"""Result summary schema for spotlight search.

ResultSummary is created by the evaluator for each search result.
These summaries are stored in history so future iterations can see
what was retrieved without including full result content.
"""

from pydantic import BaseModel, Field


class SpotlightSearchResultSummary(BaseModel):
    """Compact summary of a search result for history context.

    Created by the evaluator for each result. Stored in iteration history
    so the planner can see what was found without full result content.
    """

    entity_id: str = Field(..., description="Entity ID of the result (for deduplication).")
    name: str = Field(..., description="Title or name of the result.")
    entity_type: str = Field(
        ..., description="Entity type (e.g., 'NotionPageEntity', 'SlackMessageEntity')."
    )
    source_name: str = Field(
        ..., description="Source the result came from (e.g., 'notion', 'slack')."
    )
    content_summary: str = Field(
        ...,
        description="1-2 sentence summary of what this result contains. "
        "Focus on key facts, topics, or data points relevant to the query.",
    )
