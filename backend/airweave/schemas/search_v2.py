"""Search V2 request/response schemas."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from airweave.domains.search.types import FilterGroup, RetrievalStrategy, SearchResult


class SearchTier(str, Enum):
    """Search tiers."""

    INSTANT = "instant"
    CLASSIC = "classic"
    AGENTIC = "agentic"


class InstantSearchRequest(BaseModel):
    """Instant search request — embed query, fire at Vespa, return results."""

    query: str = Field(..., description="Search query text.")
    retrieval_strategy: RetrievalStrategy = Field(
        default=RetrievalStrategy.HYBRID,
        description="Which retrieval strategy to use.",
    )
    filter: Optional[list[FilterGroup]] = Field(
        default=None, description="Filter groups (combined with OR)."
    )
    limit: int = Field(default=100, ge=1, le=1000, description="Max results to return.")
    offset: int = Field(default=0, ge=0, description="Number of results to skip.")

    @field_validator("query")
    @classmethod
    def query_not_empty(cls, v: str) -> str:
        """Validate that query is not empty or whitespace-only."""
        if not v.strip():
            raise ValueError("Query cannot be empty")
        return v


class ClassicSearchRequest(BaseModel):
    """Classic search request — LLM generates a search plan, execute against Vespa."""

    query: str = Field(..., description="Search query text.")
    filter: Optional[list[FilterGroup]] = Field(
        default=None, description="Filter groups (combined with OR)."
    )
    limit: int = Field(default=100, ge=1, le=1000, description="Max results to return.")
    offset: int = Field(default=0, ge=0, description="Number of results to skip.")

    @field_validator("query")
    @classmethod
    def query_not_empty(cls, v: str) -> str:
        """Validate that query is not empty or whitespace-only."""
        if not v.strip():
            raise ValueError("Query cannot be empty")
        return v


class AgenticSearchRequest(BaseModel):
    """Agentic search request — full agent loop with tool calling."""

    query: str = Field(..., description="Search query text.")
    thinking: bool = Field(
        default=False, description="Enable extended thinking / chain-of-thought."
    )
    filter: Optional[list[FilterGroup]] = Field(
        default=None, description="Filter groups (combined with OR)."
    )
    limit: Optional[int] = Field(
        default=None, ge=1, description="Max results. None means agent decides."
    )

    @field_validator("query")
    @classmethod
    def query_not_empty(cls, v: str) -> str:
        """Validate that query is not empty or whitespace-only."""
        if not v.strip():
            raise ValueError("Query cannot be empty")
        return v


class SearchV2Response(BaseModel):
    """Unified response for all search tiers."""

    results: list[SearchResult] = Field(
        default_factory=list, description="Search results ordered by relevance."
    )
