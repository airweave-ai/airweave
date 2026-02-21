"""AgenticSearch plan schema.

Used as the search tool's input schema. The model's reasoning is expressed
in free-form text between tool calls, not in a schema field.
"""

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
        """Render the search query as markdown."""
        lines = [f"- Primary: `{self.primary}`"]
        if self.variations:
            variations_md = ", ".join(f"`{v}`" for v in self.variations)
            lines.append(f"- Variations: {variations_md}")
        return "\n".join(lines)


class AgenticSearchPlan(BaseModel):
    """AgenticSearch plan — the search tool's input schema."""

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
