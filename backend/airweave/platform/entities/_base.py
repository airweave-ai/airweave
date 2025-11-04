from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastembed import SparseEmbedding
from pydantic import BaseModel, ConfigDict, Field


class Breadcrumb(BaseModel):
    """Breadcrumb for tracking ancestry."""

    entity_id: str = Field(..., description="ID of the entity in the source.")


class AccessControl(BaseModel):
    """Access control metadata for an entity (source-agnostic).

    Stores who can view this entity as principal identifiers.
    Principals are NOT expanded - groups stored as-is.

    Format:
        - Users: "user:john@acme.com"
        - Groups: "group:<group_id>" (e.g., "group:engineering" or "group:uuid-123")
    """

    viewers: List[str] = Field(
        default_factory=list, description="Principal IDs who can view this entity"
    )
    is_public: bool = Field(
        default=False,
        description="Whether this entity is publicly accessible.",
    )


class AirweaveSystemMetadata(BaseModel):
    """System metadata for this entity.

    All fields are Optional to support progressive enrichment during pipeline stages.
    Each stage validates required fields are set before proceeding.
    """

    # Set during early enrichment
    source_name: Optional[str] = Field(
        None, description="Name of the source this entity belongs to."
    )
    entity_type: Optional[str] = Field(
        None, description="Type of the entity this entity represents in the source."
    )
    sync_id: Optional[UUID] = Field(None, description="ID of the sync this entity belongs to.")
    sync_job_id: Optional[UUID] = Field(
        None, description="ID of the sync job this entity belongs to."
    )

    # Set during hash computation
    hash: Optional[str] = Field(None, description="Hash of the content used for change detection.")

    # Set during chunking
    chunk_index: Optional[int] = Field(None, description="Index of the chunk in the file.")
    original_entity_id: Optional[str] = Field(
        None, description="Original entity_id before chunking (for bulk deletes)"
    )

    # Set during embedding
    vectors: Optional[List[List[float] | SparseEmbedding]] = Field(
        None, description="Vectors for this entity."
    )

    # Set during persistence
    db_entity_id: Optional[UUID] = Field(None, description="ID of the entity in the database.")
    db_created_at: Optional[datetime] = Field(
        None, description="Timestamp of when the entity was created in Airweave."
    )
    db_updated_at: Optional[datetime] = Field(
        None, description="Timestamp of when the entity was last updated in Airweave."
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)


class BaseEntity(BaseModel):
    """Base entity schema."""

    # required
    entity_id: str = Field(..., description="ID of the entity in the source.")
    breadcrumbs: List[Breadcrumb] = Field(..., description="List of breadcrumbs for this entity.")

    name: str = Field(..., description="Name of the entity.")

    created_at: Optional[datetime] = Field(
        None, description="Timestamp of when the entity was created."
    )
    updated_at: Optional[datetime] = Field(
        None, description="Timestamp of when the entity was last updated."
    )

    # filled later
    textual_representation: Optional[str] = Field(
        None, description="Textual representation of the entity to be embedded."
    )
    airweave_system_metadata: Optional[AirweaveSystemMetadata] = Field(
        None, description="System metadata for this entity."
    )

    # access control
    access: Optional[AccessControl] = Field(
        None, description="Access control - who can view this entity (not expanded)"
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)


class FileEntity(BaseEntity):
    """File entity schema."""

    url: str = Field(..., description="URL to the file.")

    size: int = Field(..., description="Size of the file in bytes.")

    file_type: str = Field(..., description="Type of the file.")
    mime_type: Optional[str] = Field(None, description="MIME type of the file.")

    local_path: Optional[str] = Field(None, description="Local path of the file.")


class PolymorphicEntity(BaseEntity):
    """Polymorphic entity schema."""

    table_name: str = Field(..., description="Name of the table this entity belongs to.")
    schema_name: str = Field(..., description="Name of the schema this entity belongs to.")
    primary_key_columns: List[str] = Field(..., description="List of primary key columns.")


class CodeFileEntity(FileEntity):
    """Code file entity schema."""

    repo_name: str = Field(..., description="Name of the repository this file belongs to.")
    path_in_repo: str = Field(..., description="Path of the file within the repository.")
    repo_owner: str = Field(..., description="Owner of the repository this file belongs to.")

    language: str = Field(..., description="Language of the code file.")

    commit_id: str = Field(..., description="Last commit ID that modified this file.")


class EmailEntity(FileEntity):
    """Base entity for email messages.

    Email messages are treated as FileEntity with HTML body saved to local file.
    Content is not stored in entity fields, only in the downloaded file.
    """

    pass


class DeletionEntity(BaseEntity):
    """Base entity that supports deletion tracking."""

    deletion_status: str = Field(
        ...,
        description="Deletion status: 'active' for normal entities, 'removed' for deleted entities",
    )


class WebEntity(BaseEntity):
    """Web entity schema."""

    crawl_url: str = Field(..., description="URL to crawl.")
