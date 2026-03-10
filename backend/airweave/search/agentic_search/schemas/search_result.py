"""Agentic search result schema."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class AgenticSearchBreadcrumb(BaseModel):
    """Breadcrumb in agentic search result."""

    entity_id: str = Field(..., description="ID of the entity in the source.")
    name: str = Field(..., description="Display name of the entity.")
    entity_type: str = Field(..., description="Entity class name (e.g., 'AsanaProjectEntity').")

    def to_md(self) -> str:
        """Render the breadcrumb as markdown."""
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
        """Render the system metadata as markdown."""
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
        """Render the access control as markdown."""
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

    def to_summary_md(self) -> str:
        """Compact metadata summary for context retention (excludes content)."""
        path = " > ".join(bc.to_md() for bc in self.breadcrumbs) if self.breadcrumbs else "(root)"
        created = self.created_at.isoformat() if self.created_at else "unknown"
        updated = self.updated_at.isoformat() if self.updated_at else "unknown"
        meta = self.airweave_system_metadata
        return (
            f"- **{self.name}** (id: {self.entity_id}, score: {self.relevance_score:.4f})\n"
            f"  Breadcrumbs: {path}\n"
            f"  Source: {meta.source_name} ({meta.entity_type}) | "
            f"Created: {created} | Updated: {updated}\n"
            f"  Original entity: {meta.original_entity_id} (chunk {meta.chunk_index})"
        )

    def to_snippet_summary_md(self) -> str:
        """Compact summary with content snippet (~100 tokens) for search results."""
        path = " > ".join(bc.to_md() for bc in self.breadcrumbs) if self.breadcrumbs else "(root)"
        meta = self.airweave_system_metadata
        created = self.created_at.isoformat() if self.created_at else "unknown"
        updated = self.updated_at.isoformat() if self.updated_at else "unknown"

        # 400-char content snippet (~100 tokens — enough to judge relevance)
        content = self.textual_representation.strip()
        total_chars = len(content)
        truncated = total_chars > 400
        snippet = (content[:397] + "...") if truncated else content

        # Chunk info (only show if chunked)
        chunk_info = ""
        if meta.chunk_index > 0:
            chunk_info = f" | Chunk {meta.chunk_index}"

        # Show how much of the content is visible
        size_info = f" [{400}/{total_chars} chars]" if truncated else ""

        return (
            f"- **{self.name}** (id: `{self.entity_id}`, score: {self.relevance_score:.4f})\n"
            f"  {meta.source_name} ({meta.entity_type}){chunk_info} | "
            f"Created: {created} | Updated: {updated}\n"
            f"  Path: {path}\n"
            f"  > {snippet}{size_info}"
        )

    def to_md(self) -> str:
        """Render the search result as markdown for LLM context."""
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

        # Breadcrumbs
        if self.breadcrumbs:
            breadcrumb_path = " > ".join(bc.to_md() for bc in self.breadcrumbs)
            lines.append(f"**Path:** {breadcrumb_path}")
        else:
            lines.append("**Path:** (root)")

        lines.append("")

        # System metadata
        lines.append("**System Metadata:**")
        lines.append(self.airweave_system_metadata.to_md())

        lines.append("")

        # Access control
        lines.append(f"**Access:** {self.access.to_md()}")

        lines.append("")

        # Full textual representation (NEVER truncated)
        lines.append("**Content:**")
        lines.append("```")
        lines.append(self.textual_representation)
        lines.append("```")

        return "\n".join(lines)

    def to_full_md(self) -> str:
        """Render the full search result as markdown including source fields."""
        lines = [self.to_md()]

        if self.url:
            lines.append("")
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


class AgenticSearchResults(BaseModel):
    """Container for search results in relevance order."""

    results: list[AgenticSearchResult] = Field(
        default_factory=list,
        description="Search results ordered by relevance (highest first).",
    )

    def __len__(self) -> int:
        """Return the number of results."""
        return len(self.results)
