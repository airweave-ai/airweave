"""Spotlight search result schema."""

import json
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

# NOTE: a lot more required than in the sync pipeline


class SpotlightBreadcrumb(BaseModel):
    """Breadcrumb in spotlight search result."""

    entity_id: str = Field(..., description="ID of the entity in the source.")
    name: str = Field(..., description="Display name of the entity.")
    entity_type: str = Field(..., description="Entity class name (e.g., 'AsanaProjectEntity').")

    def to_md(self) -> str:
        """Render the breadcrumb as markdown.

        Returns:
            Markdown string: name (entity_type) [entity_id]
        """
        return f"{self.name} ({self.entity_type}) [{self.entity_id}]"


class SpotlightSystemMetadata(BaseModel):
    """System metadata in spotlight search result."""

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


class SpotlightAccessControl(BaseModel):
    """Access control in spotlight search result."""

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


class SpotlightSearchResult(BaseModel):
    """Spotlight search result."""

    entity_id: str = Field(..., description="Original entity ID.")
    name: str = Field(..., description="Entity display name.")
    breadcrumbs: list[SpotlightBreadcrumb] = Field(
        ..., description="Breadcrumbs showing entity hierarchy."
    )

    created_at: Optional[datetime] = Field(default=None, description="When the entity was created.")
    updated_at: Optional[datetime] = Field(
        default=None, description="When the entity was last updated."
    )

    textual_representation: str = Field(..., description="Semantically searchable text content")
    airweave_system_metadata: SpotlightSystemMetadata = Field(..., description="System metadata")

    access: SpotlightAccessControl = Field(..., description="Access control")

    web_url: str = Field(
        ...,
        description="URL to view the entity in its source application (e.g., Notion, Asana).",
    )

    url: Optional[str] = Field(
        default=None,
        description="Download URL for file entities. Only present for FileEntity types.",
    )

    source_fields: dict[str, Any] = Field(
        ...,
        description="All source-specific fields.",
    )

    def to_md(self) -> str:
        """Render the full search result as markdown.

        Includes all fields with nested to_md() calls. Does not truncate any data.

        Returns:
            Markdown string with complete result information.
        """
        lines = [
            f"### {self.name}",
            "",
            f"**Entity ID:** {self.entity_id}",
            f"**Web URL:** {self.web_url}",
        ]

        if self.url:
            lines.append(f"**Download URL:** {self.url}")

        # Timestamps
        created = self.created_at.isoformat() if self.created_at else "unknown"
        updated = self.updated_at.isoformat() if self.updated_at else "unknown"
        lines.append(f"**Created:** {created}")
        lines.append(f"**Updated:** {updated}")

        # Breadcrumbs (uses SpotlightBreadcrumb.to_md())
        if self.breadcrumbs:
            breadcrumb_path = " > ".join(bc.to_md() for bc in self.breadcrumbs)
            lines.append(f"**Path:** {breadcrumb_path}")
        else:
            lines.append("**Path:** (root)")

        lines.append("")

        # System metadata (uses SpotlightSystemMetadata.to_md())
        lines.append("**System Metadata:**")
        lines.append(self.airweave_system_metadata.to_md())

        lines.append("")

        # Access control (uses SpotlightAccessControl.to_md())
        lines.append(f"**Access:** {self.access.to_md()}")

        lines.append("")

        # Full textual representation (no truncation)
        lines.append("**Content:**")
        lines.append("```")
        lines.append(self.textual_representation)
        lines.append("```")

        lines.append("")

        # Source fields (complete JSON, no truncation)
        lines.append("**Source Fields:**")
        lines.append("```json")
        lines.append(json.dumps(self.source_fields, indent=2, default=str))
        lines.append("```")

        return "\n".join(lines)
