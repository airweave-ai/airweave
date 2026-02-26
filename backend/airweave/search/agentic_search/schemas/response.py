"""Response schemas for agentic search."""

from pydantic import BaseModel

from .answer import AgenticSearchAnswer
from .search_result import AgenticSearchResult


class AgenticSearchResponse(BaseModel):
    """Response schema for agentic search."""

    results: list[AgenticSearchResult]
    answer: AgenticSearchAnswer
