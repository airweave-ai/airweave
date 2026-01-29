"""Spotlight search result schema."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

# NOTE: a lot more required than in the sync pipeline


class SpotlightBreadcrumb(BaseModel):
    """Breadcrumb in spotlight search result."""

    entity_id: str = Field(..., description="ID of the entity in the source.")
    name: str = Field(..., description="Display name of the entity.")
    entity_type: str = Field(..., description="Entity class name (e.g., 'AsanaProjectEntity').")


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


class SpotlightAccessControl(BaseModel):
    """Access control in spotlight search result."""

    viewers: Optional[list[str]] = Field(
        default=None, description="Principal IDs who can view this entity. None if unknown."
    )
    is_public: Optional[bool] = Field(
        default=None, description="Whether this entity is publicly accessible. None if unknown."
    )


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

    url: Optional[str] = Field(
        default=None,
        description="URL to view/access the entity in its source application.",
    )

    source_fields: dict[str, Any] = Field(
        ...,
        description="All source-specific fields.",
    )
