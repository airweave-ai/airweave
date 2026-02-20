"""SyncJob schema.

Sync jobs represent individual data synchronization operations that extract, transform,
and load data from source connections into searchable collections. They provide detailed
tracking of sync progress, performance metrics, and error reporting.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from airweave.models.sync_job import SyncJobStatus
from airweave.platform.sync.config.base import SyncConfig


class SyncJobBase(BaseModel):
    """Base schema for SyncJob."""

    sync_id: UUID
    status: SyncJobStatus = SyncJobStatus.PENDING
    scheduled: bool = False
    entities_inserted: Optional[int] = 0
    entities_updated: Optional[int] = 0
    entities_deleted: Optional[int] = 0
    entities_kept: Optional[int] = 0
    entities_skipped: Optional[int] = 0
    entities_encountered: Optional[dict[str, int]] = {}
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error: Optional[str] = None
    access_token: Optional[str] = None
    sync_config: Optional[SyncConfig] = None
    sync_metadata: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)


class SyncJobCreate(SyncJobBase):
    """Schema for creating a SyncJob object."""

    pass


class SyncJobUpdate(BaseModel):
    """Schema for updating a SyncJob object."""

    status: Optional[SyncJobStatus] = None
    scheduled: Optional[bool] = None
    entities_inserted: Optional[int] = None
    entities_updated: Optional[int] = None
    entities_deleted: Optional[int] = None
    entities_kept: Optional[int] = None
    entities_skipped: Optional[int] = None
    entities_encountered: Optional[dict[str, int]] = {}
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error: Optional[str] = None
    sync_metadata: Optional[dict] = None


class SyncJobInDBBase(SyncJobBase):
    """Base schema for SyncJob stored in DB."""

    id: UUID
    organization_id: UUID
    created_by_email: Optional[EmailStr] = None
    modified_by_email: Optional[EmailStr] = None
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    sync_name: Optional[str] = Field(
        None, description="Name of the sync, populated from join query"
    )

    model_config = ConfigDict(from_attributes=True)


class SyncJob(SyncJobInDBBase):
    """Schema for SyncJob."""

    def to_source_connection_job(self, source_connection_id: UUID) -> "SourceConnectionJob":
        """Convert SyncJob to SourceConnectionJob."""
        return SourceConnectionJob(
            source_connection_id=source_connection_id,
            id=self.id,
            organization_id=self.organization_id,
            created_by_email=self.created_by_email,
            modified_by_email=self.modified_by_email,
            created_at=self.created_at,
            modified_at=self.modified_at,
            status=self.status,
            scheduled=self.scheduled,
            entities_inserted=self.entities_inserted,
            entities_updated=self.entities_updated,
            entities_deleted=self.entities_deleted,
            entities_kept=self.entities_kept,
            entities_skipped=self.entities_skipped,
            entities_encountered=self.entities_encountered,
            started_at=self.started_at,
            completed_at=self.completed_at,
            failed_at=self.failed_at,
            error=self.error,
        )


class SourceConnectionJob(BaseModel):
    """Data synchronization job for a specific source connection."""

    source_connection_id: UUID = Field(
        ...,
        description=(
            "Unique identifier of the source connection for which this data refresh is running."
        ),
    )
    id: UUID = Field(
        ...,
        description="Unique identifier for this specific data refresh operation.",
    )
    organization_id: UUID = Field(
        ...,
        description="Identifier of the organization that owns this data refresh operation.",
    )
    created_by_email: Optional[EmailStr] = Field(
        None,
        description=(
            "Email address of the user who initiated this data refresh "
            "(for manually triggered operations)."
        ),
    )
    modified_by_email: Optional[EmailStr] = Field(
        None,
        description="Email address of the user who last modified this data refresh operation.",
    )
    created_at: Optional[datetime] = Field(
        None,
        description="Timestamp when this data refresh was created and queued (ISO 8601 format).",
    )
    modified_at: Optional[datetime] = Field(
        None,
        description="Timestamp when this data refresh was last modified (ISO 8601 format).",
    )
    status: SyncJobStatus = Field(
        SyncJobStatus.PENDING,
        description="Current execution status of the data refresh:<br/>"
        "• **created**: Operation has been created but not yet queued<br/>"
        "• **pending**: Operation is queued and waiting to start<br/>"
        "• **in_progress**: Currently running and processing data<br/>"
        "• **completed**: Finished successfully with all data processed<br/>"
        "• **failed**: Encountered errors and could not complete<br/>"
        "• **cancelled**: Manually cancelled before completion",
    )
    scheduled: bool = Field(
        False,
        description=(
            "Whether this data refresh was triggered by a schedule (true) or manually (false)."
        ),
    )
    entities_inserted: Optional[int] = Field(
        0,
        description=(
            "Number of new data entities that were added to the collection during this refresh."
        ),
    )
    entities_updated: Optional[int] = Field(
        0,
        description=(
            "Number of existing entities that were modified and updated during this refresh."
        ),
    )
    entities_deleted: Optional[int] = Field(
        0,
        description=(
            "Number of entities that were removed from the collection because they no longer "
            "exist in the source."
        ),
    )
    entities_kept: Optional[int] = Field(
        0,
        description=(
            "Number of entities that were checked but required no changes because they were "
            "already up-to-date."
        ),
    )
    entities_skipped: Optional[int] = Field(
        0,
        description=(
            "Number of entities that were intentionally skipped due to filtering rules or "
            "processing decisions."
        ),
    )
    entities_encountered: Optional[dict[str, int]] = Field(
        {},
        description="Detailed breakdown of entities processed by type or category.",
    )
    started_at: Optional[datetime] = Field(
        None,
        description="Timestamp when the data refresh began active processing (ISO 8601 format).",
    )
    completed_at: Optional[datetime] = Field(
        None,
        description="Timestamp when the data refresh finished successfully (ISO 8601 format).",
    )
    failed_at: Optional[datetime] = Field(
        None,
        description="Timestamp when the data refresh failed (ISO 8601 format).",
    )
    error: Optional[str] = Field(
        None,
        description="Detailed error message if the data refresh failed.",
    )
