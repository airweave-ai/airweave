"""Response schemas for agentic search."""

from pydantic import BaseModel, Field

from .answer import AgenticSearchAnswer
from .search_result import AgenticSearchResult


class AgenticSearchResponse(BaseModel):
    """Response schema for agentic search."""

    results: list[AgenticSearchResult]
    answer: AgenticSearchAnswer
    answer_found: bool = Field(
        ...,
        description="Whether the agent concluded it found an answer.",
    )
