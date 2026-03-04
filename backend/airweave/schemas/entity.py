"""Entity schema."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EntityBase(BaseModel):
    """Base schema for Entity."""

    sync_job_id: UUID
    sync_id: UUID
    entity_id: str
    entity_definition_id: Optional[UUID] = None
    hash: str

    model_config = ConfigDict(from_attributes=True)


class EntityCreate(EntityBase):
    """Schema for creating a Entity object."""

    pass


class EntityUpdate(BaseModel):
    """Schema for updating a Entity object."""

    sync_job_id: Optional[UUID] = None
    sync_id: Optional[UUID] = None
    entity_id: Optional[str] = None
    entity_definition_id: Optional[UUID] = None
    hash: Optional[str] = None


class EntityInDBBase(EntityBase):
    """Base schema for Entity stored in DB."""

    id: UUID
    organization_id: UUID
    created_at: datetime

    modified_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Entity(EntityInDBBase):
    """Schema for Entity."""

    pass


class EntityCount(BaseModel):
    """Schema for entity count."""

    count: int
