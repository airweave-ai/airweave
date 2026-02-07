"""Request schemas for spotlight search."""

from enum import Enum
from typing import List

from pydantic import BaseModel, Field, field_validator

from airweave.search.spotlight.schemas.filter import SpotlightFilterGroup


class SpotlightSearchMode(str, Enum):
    """Search execution mode.

    - DIRECT: Performs a single search pass.
    - AGENTIC: Performs an intelligent multi-step search to find the best results.
    """

    DIRECT = "direct"
    AGENTIC = "agentic"


class SpotlightRequest(BaseModel):
    """Request schema for spotlight search."""

    query: str = Field(..., description="The natural language search query.")
    filter: List[SpotlightFilterGroup] = Field(
        default_factory=list,
        description=(
            "Filter groups that are always applied to search results. "
            "Conditions within a group are combined with AND. "
            "Multiple groups are combined with OR. "
            "Leave empty for no filtering."
        ),
    )
    mode: SpotlightSearchMode = Field(
        default=SpotlightSearchMode.AGENTIC,
        description=(
            "The search mode. "
            "'direct' performs a single search pass. "
            "'agentic' performs an intelligent multi-step search to find the best results "
            "(may take longer). Defaults to 'agentic'."
        ),
    )

    @field_validator("query")
    @classmethod
    def validate_query_not_empty(cls, v: str) -> str:
        """Validate that query is not empty."""
        if not v or not v.strip():
            raise ValueError("Query cannot be empty")
        return v
