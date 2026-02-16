"""Request schemas for agentic search."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from airweave.search.agentic_search.schemas.filter import AgenticSearchFilterGroup


class AgenticSearchMode(str, Enum):
    """Search execution mode.

    - FAST: Performs a single search pass.
    - THINKING: Performs an intelligent multi-step search to find the best results.
    """

    FAST = "fast"
    THINKING = "thinking"


class AgenticSearchRequest(BaseModel):
    """Request schema for agentic search."""

    query: str = Field(..., description="The natural language search query.")
    filter: List[AgenticSearchFilterGroup] = Field(
        default_factory=list,
        description=(
            "Filter groups that are always applied to search results. "
            "Conditions within a group are combined with AND. "
            "Multiple groups are combined with OR. "
            "Leave empty for no filtering."
        ),
    )
    mode: AgenticSearchMode = Field(
        default=AgenticSearchMode.THINKING,
        description=(
            "The search mode. "
            "'fast' performs a single search pass. "
            "'thinking' performs an intelligent multi-step search to find the best results "
            "(may take longer). Defaults to 'thinking'."
        ),
    )
    limit: Optional[int] = Field(
        default=None,
        ge=1,
        description=(
            "Maximum number of results to return. The response will contain at most "
            "this many results, but the agent can decide to return fewer. "
            "When not set, all results are returned."
        ),
    )

    @field_validator("query")
    @classmethod
    def validate_query_not_empty(cls, v: str) -> str:
        """Validate that query is not empty."""
        if not v or not v.strip():
            raise ValueError("Query cannot be empty")
        return v
