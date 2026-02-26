"""Sync cursor schemas."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SyncCursorBase(BaseModel):
    """Base sync cursor schema."""

    sync_id: Optional[UUID] = Field(None, description="ID of the associated sync")
    cursor_data: Dict[str, Any] = Field(
        default_factory=dict, description="Cursor data for incremental sync"
    )
    cursor_field: Optional[str] = Field(
        None, description="The field name used as cursor (e.g., 'last_repository_pushed_at')"
    )


class SyncCursorCreate(SyncCursorBase):
    """Schema for creating a sync cursor."""

    pass


class SyncCursorUpdate(BaseModel):
    """Schema for updating a sync cursor."""

    sync_id: Optional[UUID] = Field(None, description="ID of the associated sync")
    cursor_data: Optional[Dict[str, Any]] = Field(
        None, description="Cursor data for incremental sync"
    )
    cursor_field: Optional[str] = Field(
        None, description="The field name used as cursor (e.g., 'last_repository_pushed_at')"
    )


class SyncCursor(SyncCursorBase):
    """Schema for sync cursor response."""

    id: UUID = Field(..., description="Unique identifier")
    organization_id: UUID = Field(..., description="Organization ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    modified_at: datetime = Field(..., description="Last modification timestamp")
    last_updated: datetime = Field(..., description="Last cursor update timestamp")
    cursor_field: Optional[str] = Field(
        None, description="The field name used as cursor (e.g., 'last_repository_pushed_at')"
    )

    model_config = ConfigDict(from_attributes=True)
