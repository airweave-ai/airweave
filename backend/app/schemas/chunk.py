"""Chunk schema."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ChunkBase(BaseModel):
    """Base schema for Chunk."""

    sync_job_id: UUID
    sync_id: UUID
    entity_id: str
    hash: str

    class Config:
        """Pydantic config for ChunkBase."""

        from_attributes = True


class ChunkCreate(ChunkBase):
    """Schema for creating a Chunk object."""

    pass


class ChunkUpdate(BaseModel):
    """Schema for updating a Chunk object."""

    sync_job_id: Optional[UUID] = None
    sync_id: Optional[UUID] = None
    entity_id: Optional[str] = None
    hash: Optional[str] = None


class ChunkInDBBase(ChunkBase):
    """Base schema for Chunk stored in DB."""

    id: UUID
    organization_id: UUID
    created_at: datetime
    modified_at: datetime

    class Config:
        """Pydantic config for ChunkInDBBase."""

        from_attributes = True


class Chunk(ChunkInDBBase):
    """Schema for Chunk."""

    pass
