"""SyncJob schema."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from airweave.models.sync_job import SyncJobStatus


class SyncJobBase(BaseModel):
    """Base schema for SyncJob."""

    sync_id: UUID
    status: SyncJobStatus = SyncJobStatus.PENDING
    entities_inserted: Optional[int] = 0
    entities_updated: Optional[int] = 0
    entities_deleted: Optional[int] = 0
    entities_kept: Optional[int] = 0
    entities_skipped: Optional[int] = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error: Optional[str] = None

    class Config:
        """Pydantic config for SyncJobBase."""

        from_attributes = True


class SyncJobCreate(SyncJobBase):
    """Schema for creating a SyncJob object."""

    pass


class SyncJobUpdate(BaseModel):
    """Schema for updating a SyncJob object."""

    status: Optional[SyncJobStatus] = None
    entities_inserted: Optional[int] = None
    entities_updated: Optional[int] = None
    entities_deleted: Optional[int] = None
    entities_kept: Optional[int] = None
    entities_skipped: Optional[int] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None


class SyncJobInDBBase(SyncJobBase):
    """Base schema for SyncJob stored in DB."""

    id: UUID
    organization_id: UUID
    created_by_email: EmailStr
    modified_by_email: EmailStr
    created_at: datetime
    modified_at: datetime
    sync_name: Optional[str] = Field(
        None, description="Name of the sync, populated from join query"
    )

    class Config:
        """Pydantic config for SyncJobInDBBase."""

        from_attributes = True


class SyncJob(SyncJobInDBBase):
    """Schema for SyncJob."""

    pass
