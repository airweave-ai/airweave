"""Response schemas for spotlight search."""

from pydantic import BaseModel

from airweave.search.spotlight.schemas.answer import Answer
from airweave.search.spotlight.schemas.search_result import SpotlightSearchResult


class SpotlightResponse(BaseModel):
    """Response schema for spotlight search."""

    results: list[SpotlightSearchResult]
    answer: Answer
