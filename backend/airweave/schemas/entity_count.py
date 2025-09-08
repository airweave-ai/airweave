"""Entity count schema."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class EntityCountBase(BaseModel):
    """Base schema for EntityCount."""

    sync_id: UUID
    entity_definition_id: UUID
    count: int

    class Config:
        """Pydantic config."""

        from_attributes = True


class EntityCountCreate(EntityCountBase):
    """Schema for creating an EntityCount object."""

    pass


class EntityCountUpdate(BaseModel):
    """Schema for updating an EntityCount object."""

    count: Optional[int] = None


class EntityCount(EntityCountBase):
    """Schema for EntityCount with all fields."""

    id: UUID

    class Config:
        """Pydantic config."""

        from_attributes = True


class EntityCountWithDefinition(BaseModel):
    """Entity count with entity definition details."""

    count: int
    entity_definition_id: UUID
    entity_definition_name: str
    entity_definition_type: str
    entity_definition_description: Optional[str] = None

    class Config:
        """Pydantic config."""

        from_attributes = True
