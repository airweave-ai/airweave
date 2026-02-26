"""AgenticSearch plan schema."""

from typing import List

from pydantic import BaseModel, Field

from .filter import AgenticSearchFilterGroup
from .retrieval_strategy import AgenticSearchRetrievalStrategy


class AgenticSearchQuery(BaseModel):
    """Agentic search query."""

    primary: str = Field(
        ...,
        description="Primary query used for both semantic (dense) AND keyword (BM25) search. "
        "Should be keyword-optimized.",
    )
    variations: list[str] = Field(
        default_factory=list,
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


class AgenticSearchPlan(BaseModel):
    """AgenticSearch plan.

    Field order matters — the model generates JSON fields sequentially.
    By placing reasoning first, the model must think through the strategy ledger
    and articulate its plan BEFORE committing to parameters. This prevents
    post-hoc rationalization.
    """

    reasoning: str = Field(
        ...,
        description=(
            "Your reasoning as natural inner monologue — think out loud. "
            "e.g. 'Let me try a hybrid search here since the query is broad...', "
            "'Hmm, the keyword search missed it — maybe the document uses different wording...' "
            "Don't restate the user query or collection info. "
            "Focus on: what changed from the last iteration, why this approach, "
            "what you expect to find. Be incremental, not exhaustive."
        ),
    )
    query: AgenticSearchQuery = Field(..., description="Search query.")
    filter_groups: List[AgenticSearchFilterGroup] = Field(
        default_factory=list,
        description=(
            "Filter groups to narrow the search space. "
            "Conditions within a group are combined with AND. "
            "Multiple groups are combined with OR. "
            "Leave empty for no filtering."
        ),
    )
    limit: int = Field(..., ge=1, le=200, description="Maximum number of results to return.")
    offset: int = Field(..., ge=0, description="Number of results to skip (for pagination).")
    retrieval_strategy: AgenticSearchRetrievalStrategy = Field(
        ...,
        description="The retrieval strategy. 'semantic': returns conceptually similar "
        "chunks even without exact term matches — best for exploration and filter-based "
        "retrieval (e.g., by original_entity_id, chunk_index, breadcrumbs). 'keyword': "
        "returns ONLY chunks containing the query terms — precise but will silently "
        "exclude chunks that match filters but lack the query words. 'hybrid': combines "
        "both (chunk can match via either) — good default but keyword still influences "
        "results. ALWAYS use 'semantic' when filtering by original_entity_id or "
        "chunk_index to get all chunks of a document.",
    )

    def to_md(self) -> str:
        """Render the plan as markdown for history context.

        Uses nested to_md() methods for query and filter groups.

        Returns:
            Markdown string representing this plan.
        """
        lines = ["**Plan:**"]

        lines.append(f"- Reasoning: {self.reasoning}")

        # Query (uses AgenticSearchQuery.to_md())
        lines.append("**Query:**")
        lines.append(self.query.to_md())

        lines.append(f"- Strategy: {self.retrieval_strategy.value}")
        lines.append(f"- Limit: {self.limit}, Offset: {self.offset}")

        # Filter groups (uses AgenticSearchFilterGroup.to_md())
        if self.filter_groups:
            lines.append("- Filters:")
            for i, group in enumerate(self.filter_groups, 1):
                prefix = "  - " if i == 1 else "  - OR "
                lines.append(f"{prefix}{group.to_md()}")
        else:
            lines.append("- Filters: none")

        return "\n".join(lines)
