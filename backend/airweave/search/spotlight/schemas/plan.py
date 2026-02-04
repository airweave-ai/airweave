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

    def to_md(self) -> str:
        """Render the search query as markdown.

        Returns:
            Markdown string with primary query and variations.
        """
        lines = [f"- Primary: `{self.primary}`"]
        if self.variations:
            variations_md = ", ".join(f"`{v}`" for v in self.variations)
            lines.append(f"- Variations: {variations_md}")
        return "\n".join(lines)


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

    def to_md(self) -> str:
        """Render the plan as markdown for history context.

        Uses nested to_md() methods for query and filter groups.

        Returns:
            Markdown string representing this plan.
        """
        lines = ["**Plan:**"]

        # Query (uses SpotlightSearchQuery.to_md())
        lines.append("**Query:**")
        lines.append(self.query.to_md())

        lines.append(f"- Strategy: {self.retrieval_strategy.value}")
        lines.append(f"- Limit: {self.limit}, Offset: {self.offset}")

        # Filter groups (uses SpotlightFilterGroup.to_md())
        if self.filter_groups:
            lines.append("- Filters:")
            for i, group in enumerate(self.filter_groups, 1):
                prefix = "  - " if i == 1 else "  - OR "
                lines.append(f"{prefix}{group.to_md()}")
        else:
            lines.append("- Filters: none")

        lines.append(f"- Reasoning: {self.reasoning}")

        return "\n".join(lines)
