"""Agentic search result schema."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterator, Optional

from pydantic import BaseModel, Field

from airweave.search.agentic_search.external.tokenizer.interface import (
    AgenticSearchTokenizerInterface,
)

# NOTE: a lot more required than in the sync pipeline

# Module-level constants for results formatting
NO_RESULTS_MESSAGE = "No search results returned."
RESULTS_TRUNCATION_NOTICE = "\n*(Additional results truncated to fit context window)*"
RESULTS_FULLY_TRUNCATED_NOTICE = (
    "*(Search results exist but were truncated to fit context window. "
    "Results were found but details are not shown.)*"
)


class AgenticSearchBreadcrumb(BaseModel):
    """Breadcrumb in agentic search result."""

    entity_id: str = Field(..., description="ID of the entity in the source.")
    name: str = Field(..., description="Display name of the entity.")
    entity_type: str = Field(..., description="Entity class name (e.g., 'AsanaProjectEntity').")

    def to_md(self) -> str:
        """Render the breadcrumb as markdown.

        Returns:
            Markdown string: name (entity_type) [entity_id]
        """
        return f"{self.name} ({self.entity_type}) [{self.entity_id}]"


class AgenticSearchSystemMetadata(BaseModel):
    """System metadata in agentic search result."""

    source_name: str = Field(..., description="Name of the source this entity belongs to.")
    entity_type: str = Field(
        ..., description="Type of the entity this entity represents in the source."
    )
    sync_id: str = Field(..., description="ID of the sync this entity belongs to.")
    sync_job_id: str = Field(..., description="ID of the sync job this entity belongs to.")

    chunk_index: int = Field(..., description="Index of the chunk in the file.")
    original_entity_id: str = Field(..., description="Original entity ID")

    def to_md(self) -> str:
        """Render the system metadata as markdown.

        Returns:
            Markdown string with all metadata fields.
        """
        lines = [
            f"- Source: {self.source_name}",
            f"- Entity Type: {self.entity_type}",
            f"- Sync ID: {self.sync_id}",
            f"- Sync Job ID: {self.sync_job_id}",
            f"- Chunk Index: {self.chunk_index}",
            f"- Original Entity ID: {self.original_entity_id}",
        ]
        return "\n".join(lines)


class AgenticSearchAccessControl(BaseModel):
    """Access control in agentic search result."""

    viewers: Optional[list[str]] = Field(
        default=None, description="Principal IDs who can view this entity. None if unknown."
    )
    is_public: Optional[bool] = Field(
        default=None, description="Whether this entity is publicly accessible. None if unknown."
    )

    def to_md(self) -> str:
        """Render the access control as markdown.

        When both fields are None, the entity has no explicit ACL (visible to all).

        Returns:
            Markdown string with access info.
        """
        # None means no ACL set (visible to all)
        if self.is_public is None and self.viewers is None:
            return "No ACL (visible to all)"

        is_public_str = str(self.is_public) if self.is_public is not None else "not set"
        if self.viewers:
            viewers_str = ", ".join(self.viewers)
        else:
            viewers_str = "not set" if self.viewers is None else "empty list"
        return f"Public: {is_public_str}, Viewers: [{viewers_str}]"


class AgenticSearchResult(BaseModel):
    """Agentic search result."""

    entity_id: str = Field(..., description="Original entity ID.")
    name: str = Field(..., description="Entity display name.")
    relevance_score: float = Field(..., description="Relevance score from the search engine.")
    breadcrumbs: list[AgenticSearchBreadcrumb] = Field(
        ..., description="Breadcrumbs showing entity hierarchy."
    )

    created_at: Optional[datetime] = Field(default=None, description="When the entity was created.")
    updated_at: Optional[datetime] = Field(
        default=None, description="When the entity was last updated."
    )

    textual_representation: str = Field(..., description="Semantically searchable text content")
    airweave_system_metadata: AgenticSearchSystemMetadata = Field(
        ..., description="System metadata"
    )

    access: AgenticSearchAccessControl = Field(..., description="Access control")

    web_url: str = Field(
        ...,
        description="URL to view the entity in its source application (e.g., Notion, Asana).",
    )

    url: Optional[str] = Field(
        default=None,
        description="Download URL for file entities. Only present for FileEntity types.",
    )

    raw_source_fields: dict[str, Any] = Field(
        ...,
        description="All source-specific fields.",
    )

    def to_md(self) -> str:
        """Render the search result as markdown for LLM context.

        Includes base metadata, system metadata, access control, and the FULL
        textual representation. Omits source-specific fields (already captured
        in textual_representation) and download URLs (massive S3 pre-signed URLs)
        to maximize how many results fit in the context window.

        Returns:
            Markdown string with essential result information.
        """
        lines = [
            f"### {self.name}",
            "",
            f"**Entity ID:** {self.entity_id}",
            f"**Relevance Score:** {self.relevance_score:.4f}",
        ]

        # Web URL — strip query params from long URLs (S3 pre-signed URLs)
        web_url_display = self.web_url
        if len(web_url_display) > 200:
            web_url_display = web_url_display.split("?")[0]
        lines.append(f"**Web URL:** {web_url_display}")

        # Timestamps
        created = self.created_at.isoformat() if self.created_at else "unknown"
        updated = self.updated_at.isoformat() if self.updated_at else "unknown"
        lines.append(f"**Created:** {created}")
        lines.append(f"**Updated:** {updated}")

        # Breadcrumbs (uses AgenticSearchBreadcrumb.to_md())
        if self.breadcrumbs:
            breadcrumb_path = " > ".join(bc.to_md() for bc in self.breadcrumbs)
            lines.append(f"**Path:** {breadcrumb_path}")
        else:
            lines.append("**Path:** (root)")

        lines.append("")

        # System metadata (uses AgenticSearchSystemMetadata.to_md())
        lines.append("**System Metadata:**")
        lines.append(self.airweave_system_metadata.to_md())

        lines.append("")

        # Access control (uses AgenticSearchAccessControl.to_md())
        lines.append(f"**Access:** {self.access.to_md()}")

        lines.append("")

        # Full textual representation (NEVER truncated)
        lines.append("**Content:**")
        lines.append("```")
        lines.append(self.textual_representation)
        lines.append("```")

        return "\n".join(lines)

    def to_full_md(self) -> str:
        """Render the full search result as markdown including source fields.

        Includes everything from to_md() plus source-specific fields and download URLs.
        Used for debugging and detailed inspection, NOT for LLM context (too large).

        Returns:
            Markdown string with complete result information.
        """
        lines = [self.to_md()]

        if self.url:
            lines.append("")
            # Strip query params from download URLs too
            url_display = self.url
            if len(url_display) > 200:
                url_display = url_display.split("?")[0]
            lines.append(f"**Download URL:** {url_display}")

        lines.append("")
        lines.append("**Source Fields:**")
        lines.append("```json")
        lines.append(json.dumps(self.raw_source_fields, indent=2, default=str))
        lines.append("```")

        return "\n".join(lines)


@dataclass
class ResultsSectionInfo:
    """Information about the rendered results section.

    Returned by build_results_section so callers (evaluator, composer)
    know exactly how many results were included vs truncated.
    """

    markdown: str
    results_shown: int
    results_total: int


class AgenticSearchResults(BaseModel):
    """Container for search results with budget-aware rendering.

    Results are stored in relevance order (highest first, as returned by Vespa).
    """

    results: list[AgenticSearchResult] = Field(
        default_factory=list,
        description="Search results ordered by relevance (highest first).",
    )

    def __len__(self) -> int:
        """Return the number of results."""
        return len(self.results)

    @classmethod
    def get_truncation_reserve_tokens(cls, tokenizer: AgenticSearchTokenizerInterface) -> int:
        """Get the maximum tokens needed for truncation notices.

        Use this when calculating budget to ensure truncation notices always fit.

        Args:
            tokenizer: Tokenizer for counting tokens.

        Returns:
            Maximum tokens needed for either truncation notice.
        """
        return max(
            tokenizer.count_tokens(RESULTS_TRUNCATION_NOTICE),
            tokenizer.count_tokens(RESULTS_FULLY_TRUNCATED_NOTICE),
        )

    @classmethod
    def build_results_section(
        cls,
        results: AgenticSearchResults | None,
        tokenizer: AgenticSearchTokenizerInterface,
        budget: int,
    ) -> ResultsSectionInfo:
        """Build results markdown within token budget, handling None case.

        This is the main entry point for the evaluator/composer to get results
        markdown. Handles the case where results is None (search not yet executed).

        Args:
            results: The results object, or None if search not executed.
            tokenizer: Tokenizer for counting tokens.
            budget: Maximum tokens for results content.

        Returns:
            ResultsSectionInfo with markdown, results_shown, and results_total.
        """
        if results is None or len(results) == 0:
            return ResultsSectionInfo(
                markdown=NO_RESULTS_MESSAGE,
                results_shown=0,
                results_total=0,
            )

        markdown, results_shown = results.to_md_with_budget(tokenizer, budget)
        return ResultsSectionInfo(
            markdown=markdown,
            results_shown=results_shown,
            results_total=len(results),
        )

    def iter_by_relevance(self) -> Iterator[AgenticSearchResult]:
        """Iterate over results from highest to lowest relevance.

        Results are already stored in relevance order from Vespa.

        Yields:
            AgenticSearchResult objects in descending relevance order.
        """
        yield from self.results

    def to_md_with_budget(
        self,
        tokenizer: AgenticSearchTokenizerInterface,
        budget: int,
    ) -> tuple[str, int]:
        """Build results markdown within the token budget.

        Results are added by relevance (highest first) until budget is exhausted.
        If truncation occurs, a notice is appended. The caller should reserve
        tokens for the truncation notice in their budget calculation using
        `AgenticSearchResults.get_truncation_reserve_tokens()`.

        Args:
            tokenizer: Tokenizer for counting tokens.
            budget: Maximum tokens for results content.

        Returns:
            Tuple of (markdown string, number of results included).
        """
        result_parts: list[str] = []
        tokens_used = 0
        results_included = 0

        for result in self.iter_by_relevance():
            result_md = result.to_md()
            result_tokens = tokenizer.count_tokens(result_md)

            # Check if adding this result would exceed budget
            if tokens_used + result_tokens > budget:
                # Add truncation notice
                if result_parts:
                    result_parts.append(RESULTS_TRUNCATION_NOTICE)
                break

            result_parts.append(result_md)
            tokens_used += result_tokens
            results_included += 1

        # If we couldn't fit any results, indicate that
        if not result_parts:
            return RESULTS_FULLY_TRUNCATED_NOTICE, 0

        # Add header with counts
        total = len(self.results)
        header = f"**{results_included} of {total} results shown** (by relevance):\n\n"

        return header + "\n\n---\n\n".join(result_parts), results_included


@dataclass
class ResultBriefEntry:
    """A single entry in a ResultBrief.

    Contains just enough metadata for the planner to know what was found
    and to build filters for exploration. Includes parent breadcrumb info
    so the planner can filter by breadcrumb entity_type, entity_id, or name.
    """

    name: str
    source_name: str
    entity_type: str
    original_entity_id: str
    chunk_index: int
    relevance_score: float
    breadcrumb_path: str
    parent_breadcrumb_name: Optional[str] = None
    parent_breadcrumb_entity_type: Optional[str] = None
    parent_breadcrumb_entity_id: Optional[str] = None


@dataclass
class ResultBrief:
    """Deterministic summary of search results for history.

    Built from raw search results without any LLM involvement.
    Compact (~200 tokens for 10 entries) vs LLM-generated summaries (~800+ tokens).
    """

    total_count: int
    entries: list[ResultBriefEntry]

    def to_md(self) -> str:
        """Render the result brief as markdown for planner history.

        Returns:
            Compact markdown summary of what was found.
        """
        if not self.entries:
            return "**Results:** 0 found"

        lines = [f"**Results ({self.total_count} found):**"]
        for i, entry in enumerate(self.entries, 1):
            parent_info = ""
            if entry.parent_breadcrumb_name:
                parent_info = (
                    f" | parent: {entry.parent_breadcrumb_name} "
                    f"({entry.parent_breadcrumb_entity_type})"
                    f" [{entry.parent_breadcrumb_entity_id}]"
                )
            lines.append(
                f"{i}. **{entry.name}** ({entry.entity_type} from {entry.source_name}) "
                f"— score {entry.relevance_score:.3f}, "
                f"chunk {entry.chunk_index} of `{entry.original_entity_id}` | "
                f"path: {entry.breadcrumb_path}{parent_info}"
            )
        return "\n".join(lines)
