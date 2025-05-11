"""EmbeddingModel schema."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from airweave.platform.auth.schemas import AuthType
from airweave.platform.configs._base import Fields


class EmbeddingModelBase(BaseModel):
    """Base schema for EmbeddingModel."""

    name: str
    short_name: str
    description: Optional[str] = None
    provider: str
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    auth_type: Optional[AuthType] = None
    auth_config_class: Optional[str] = None

    class Config:
        """Pydantic config for EmbeddingModelBase."""

        from_attributes = True


class EmbeddingModelCreate(EmbeddingModelBase):
    """Schema for creating an EmbeddingModel object."""

    pass


class EmbeddingModelUpdate(EmbeddingModelBase):
    """Schema for updating an EmbeddingModel object."""

    pass


class EmbeddingModelInDBBase(EmbeddingModelBase):
    """Base schema for EmbeddingModel stored in DB."""

    id: UUID
    created_at: datetime
    modified_at: datetime

    class Config:
        """Pydantic config for EmbeddingModelInDBBase."""

        from_attributes = True


class EmbeddingModel(EmbeddingModelInDBBase):
    """Schema for EmbeddingModel."""

    pass


class EmbeddingModelWithAuthenticationFields(EmbeddingModel):
    """Schema for EmbeddingModel with auth config."""

    auth_fields: Fields | None = None
