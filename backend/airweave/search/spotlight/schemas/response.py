"""Response schemas for spotlight search."""

from pydantic import BaseModel

from .answer import SpotlightAnswer
from .search_result import SpotlightSearchResult


class SpotlightResponse(BaseModel):
    """Response schema for spotlight search."""

    results: list[SpotlightSearchResult]
    answer: SpotlightAnswer
