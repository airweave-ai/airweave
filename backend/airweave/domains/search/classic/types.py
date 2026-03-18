"""Types for classic search — LLM-generated search strategy."""

from __future__ import annotations

from pydantic import BaseModel, Field

from airweave.domains.search.types.filters import FilterGroup
from airweave.domains.search.types.plan import RetrievalStrategy, SearchQuery


class ClassicSearchStrategy(BaseModel):
    """LLM-generated search strategy for classic search.

    The LLM generates query expansions, retrieval strategy, and optional filters.
    Limit and offset come from the user request, not the LLM.
    """

    query: SearchQuery = Field(..., description="Search query with primary and variations.")
    retrieval_strategy: RetrievalStrategy = Field(
        ...,
        description="The retrieval strategy: 'semantic', 'keyword', or 'hybrid'.",
    )
    filter_groups: list[FilterGroup] = Field(
        default_factory=list,
        description=(
            "Optional filter groups to narrow the search space. "
            "Conditions within a group are combined with AND. "
            "Multiple groups are combined with OR. "
            "Leave empty for no filtering — when in doubt, do NOT filter."
        ),
    )
