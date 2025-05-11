"""Entity schema."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class EntityBase(BaseModel):
    """Base schema for Entity."""

    sync_job_id: UUID
    sync_id: UUID
    entity_id: str
    hash: str

    class Config:
        """Pydantic config for EntityBase."""

        from_attributes = True


class EntityCreate(EntityBase):
    """Schema for creating a Entity object."""

    pass


class EntityUpdate(BaseModel):
    """Schema for updating a Entity object."""

    sync_job_id: Optional[UUID] = None
    sync_id: Optional[UUID] = None
    entity_id: Optional[str] = None
    hash: Optional[str] = None


class EntityInDBBase(EntityBase):
    """Base schema for Entity stored in DB."""

    id: UUID
    organization_id: UUID
    created_at: datetime

    modified_at: datetime

    class Config:
        """Pydantic config for EntityInDBBase."""

        from_attributes = True


class Entity(EntityInDBBase):
    """Schema for Entity."""

    pass


class EntityCount(BaseModel):
    """Schema for entity count."""

    count: int
