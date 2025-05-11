"""Source schema."""

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, field_serializer, field_validator

from airweave.platform.auth.schemas import AuthType
from airweave.platform.configs._base import Fields


class SourceBase(BaseModel):
    """Base schema for Source."""

    name: str
    description: Optional[str] = None
    auth_type: Optional[AuthType] = None
    auth_config_class: Optional[str] = None
    short_name: str
    class_name: str
    output_entity_definition_ids: Optional[List[UUID]] = None
    organization_id: Optional[UUID] = None
    config_schema: Optional[dict] = None
    labels: Optional[List[str]] = None

    @field_serializer("output_entity_definition_ids")
    def serialize_output_entity_definition_ids(
        self, output_entity_definition_ids: Optional[List[UUID]]
    ) -> Optional[List[str]]:
        """Convert UUID list to string list during serialization."""
        if output_entity_definition_ids is None:
            return None
        return [str(uuid) for uuid in output_entity_definition_ids]

    @field_validator("output_entity_definition_ids", mode="before")
    @classmethod
    def validate_output_entity_definition_ids(cls, value: Any) -> Optional[List[UUID]]:
        """Convert string list to UUID list during deserialization."""
        if value is None:
            return None
        if isinstance(value, list):
            return [UUID(str(item)) if not isinstance(item, UUID) else item for item in value]
        return value

    class Config:
        """Pydantic config for SourceBase."""

        from_attributes = True


class SourceCreate(SourceBase):
    """Schema for creating a Source object."""

    pass


class SourceUpdate(SourceBase):
    """Schema for updating a Source object."""

    pass


class SourceInDBBase(SourceBase):
    """Base schema for Source stored in DB."""

    id: UUID
    created_at: datetime
    modified_at: datetime

    class Config:
        """Pydantic config for SourceInDBBase."""

        from_attributes = True


class Source(SourceInDBBase):
    """Schema for Source."""

    pass


class SourceWithAuthenticationFields(Source):
    """Schema for Source with auth config."""

    auth_fields: Fields | None = None
