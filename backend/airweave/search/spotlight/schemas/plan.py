"""Spotlight plan schema."""

from typing import List

from pydantic import BaseModel, Field

from .filter import SpotlightFilterGroup
from .retrieval_strategy import SpotlightRetrievalStrategy


class SpotlightSearchQuery(BaseModel):
    """Spotlight search query."""

    primary: str = Field(
        ...,
        description="Primary query used for both semantic (dense) AND keyword (BM25) search. "
        "Should be keyword-optimized.",
    )
    variations: list[str] = Field(
        default_factory=list,
        max_length=4,
        description="Additional query variations for semantic search only. "
        "Useful for paraphrases, synonyms, or alternative phrasings.",
    )


class SpotlightPlan(BaseModel):
    """Spotlight plan."""

    query: SpotlightSearchQuery = Field(..., description="Search query.")
    filter_groups: List[SpotlightFilterGroup] = Field(
        default_factory=list,
        description=(
            "Filter groups to narrow the search space. "
            "Conditions within a group are combined with AND. "
            "Multiple groups are combined with OR. "
            "Leave empty for no filtering."
        ),
    )
    limit: int = Field(..., ge=1, description="Maximum number of results to return.")
    offset: int = Field(..., ge=0, description="Number of results to skip (for pagination).")
    retrieval_strategy: SpotlightRetrievalStrategy = Field(
        ...,
        description="The retrieval strategy: 'semantic' for vector similarity, "
        "'keyword' for BM25 text matching, 'hybrid' for both combined.",
    )
    reasoning: str = Field(
        ...,
        description=(
            "Explain your search plan: why these queries, filters, and strategy? "
            "What are you trying to find and why do you think this approach will work?"
        ),
    )
