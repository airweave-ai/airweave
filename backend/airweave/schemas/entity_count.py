"""Entity count schema."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EntityCountBase(BaseModel):
    """Base schema for EntityCount."""

    sync_id: UUID
    entity_definition_short_name: str
    count: int

    model_config = ConfigDict(from_attributes=True)


class EntityCountCreate(EntityCountBase):
    """Schema for creating an EntityCount object."""

    pass


class EntityCountUpdate(BaseModel):
    """Schema for updating an EntityCount object."""

    count: Optional[int] = None


class EntityCount(EntityCountBase):
    """Schema for EntityCount with all fields."""

    id: UUID

    model_config = ConfigDict(from_attributes=True)


class EntityCountWithDefinition(BaseModel):
    """Entity count with entity definition details.

    After the entity_definition table elimination, name/type/description
    are populated from the in-memory registry or derived from the short_name.
    """

    count: int
    entity_definition_short_name: str
    entity_definition_name: str
    entity_definition_type: str
    entity_definition_description: Optional[str] = None
    modified_at: datetime

    model_config = ConfigDict(from_attributes=True)
