from datetime import datetime
from typing import Any, ClassVar, List, Optional, Type
from uuid import UUID

from fastembed import SparseEmbedding
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Breadcrumb(BaseModel):
    """Breadcrumb for tracking ancestry.

    Tracks the full context of an entity's location in the hierarchy,
    including the entity ID, human-readable name, and entity type.
    This enables rich textual representations like "Location: Workspace X → Project Y".
    """

    entity_id: str = Field(..., description="ID of the entity in the source.")
    name: str = Field(..., description="Display name of the entity.")
    entity_type: str = Field(..., description="Entity class name (e.g., 'AsanaProjectEntity').")


class AccessControl(BaseModel):
    """Access control metadata for an entity (source-agnostic).

    Stores who can view this entity as principal identifiers.
    Principals are NOT expanded - groups stored as-is.

    Format:
        - Users: "user:john@acme.com"
        - Groups: "group:<group_id>" (e.g., "group:engineering" or "group:uuid-123")

    Note: Only sources with supports_access_control=True should set this field.
    Sources without access control support should leave this as None.
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
    dense_embedding: Optional[List[float]] = Field(
        None, description="3072-dim dense embedding from text-embedding-3-large"
    )
    sparse_embedding: Optional[SparseEmbedding] = Field(
        None, description="BM25 sparse embedding for hybrid search (Qdrant only)"
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

    # Populated from flagged fields by entity pipeline (composition over inheritance)
    entity_id: Optional[str] = Field(None, description="ID of the entity in the source.")
    breadcrumbs: Optional[List[Breadcrumb]] = Field(None, description="List of breadcrumbs.")
    name: Optional[str] = Field(None, description="Name of the entity.")

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

    # Access control - only set by sources with supports_access_control=True
    access: Optional[AccessControl] = Field(
        None, description="Access control - who can view this entity (not expanded)"
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode="after")
    def validate_flagged_fields(self) -> "BaseEntity":  # noqa: C901
        """Validate that exactly one field has each unique flag.

        This enforces composition over inheritance by ensuring entity definitions
        properly flag their fields (is_entity_id, is_name, etc.).
        """
        from airweave.core.shared_models import AirweaveFieldFlag

        # Define which flags must be unique (and validate their presence)
        unique_flags = [
            AirweaveFieldFlag.IS_ENTITY_ID,
            AirweaveFieldFlag.IS_NAME,
        ]

        for flag in unique_flags:
            flag_key = flag.value if hasattr(flag, "value") else flag
            flag_label = flag.value if hasattr(flag, "value") else str(flag)
            flagged_fields = []

            # Find all fields with this flag
            for field_name, field_info in self.__class__.model_fields.items():
                json_extra = field_info.json_schema_extra
                if json_extra and isinstance(json_extra, dict):
                    if json_extra.get(flag_key):
                        flagged_fields.append(field_name)

            # Validate exactly one field has this flag
            if len(flagged_fields) == 0:
                raise ValueError(
                    f"{self.__class__.__name__} must have exactly ONE field marked with "
                    f"{flag_label}. Found 0. Please add AirweaveField(..., {flag_label}=True) "
                    f"to the appropriate field (e.g., 'gid', 'id', 'name')."
                )
            elif len(flagged_fields) > 1:
                raise ValueError(
                    f"{self.__class__.__name__} has multiple fields marked with {flag_label}: "
                    f"{', '.join(flagged_fields)}. Only ONE field can have this flag."
                )

            # Validate the flagged field is not Optional in type definition
            flagged_field_name = flagged_fields[0]
            field_info = self.__class__.model_fields[flagged_field_name]
            if field_info.is_required() is False:
                raise ValueError(
                    f"{self.__class__.__name__}.{flagged_field_name} is marked with {flag_label} "
                    f"but is defined as Optional. Required flagged fields must not be Optional. "
                    f"Change to: {flagged_field_name}: str = AirweaveField(..., {flag_label}=True)"
                )

            # Validate the flagged field has a value
            flagged_value = getattr(self, flagged_field_name, None)
            if flagged_value is None:
                raise ValueError(
                    f"{self.__class__.__name__}.{flagged_field_name} is marked with {flag_label} "
                    f"but has no value. Required flagged fields must not be None."
                )

        # Optional timestamp flags: at most one field (value can be None)
        optional_flags = [
            AirweaveFieldFlag.IS_CREATED_AT,
            AirweaveFieldFlag.IS_UPDATED_AT,
        ]

        for flag in optional_flags:
            flag_key = flag.value if hasattr(flag, "value") else flag
            flag_label = flag.value if hasattr(flag, "value") else str(flag)
            flagged_fields = []

            # Find all fields with this flag
            for field_name, field_info in self.__class__.model_fields.items():
                json_extra = field_info.json_schema_extra
                if json_extra and isinstance(json_extra, dict):
                    if json_extra.get(flag_key):
                        flagged_fields.append(field_name)

            # Validate at most one field has this flag
            if len(flagged_fields) > 1:
                raise ValueError(
                    f"{self.__class__.__name__} has multiple fields marked with {flag_label}: "
                    f"{', '.join(flagged_fields)}. Only ONE field can have this flag."
                )

        # Validate breadcrumbs is not None (must be a list, can be empty for root entities)
        if self.breadcrumbs is None:
            raise ValueError(
                f"{self.__class__.__name__} has breadcrumbs=None. "
                f"Breadcrumbs must be a list (can be empty for root entities)."
            )

        return self


class FileEntity(BaseEntity):
    """File entity schema."""

    url: str = Field(..., description="URL to the file.")

    size: int = Field(..., description="Size of the file in bytes.")

    file_type: str = Field(..., description="Type of the file.")
    mime_type: Optional[str] = Field(None, description="MIME type of the file.")

    local_path: Optional[str] = Field(None, description="Local path of the file.")


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

    deletes_entity_class: ClassVar[Optional[Type["BaseEntity"]]] = None

    deletion_status: str = Field(
        ...,
        description="Deletion status: 'active' for normal entities, 'removed' for deleted entities",
    )


class WebEntity(BaseEntity):
    """Web entity schema."""

    crawl_url: str = Field(..., description="URL to crawl.")
