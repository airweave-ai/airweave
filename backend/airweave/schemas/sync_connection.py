"""Schemas for sync connection (destination multiplexing)."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from airweave.models.sync_connection import DestinationRole


class SyncConnectionBase(BaseModel):
    """Base schema for sync connection."""

    sync_id: UUID
    connection_id: UUID
    role: DestinationRole = DestinationRole.ACTIVE

    class Config:
        """Pydantic config."""

        from_attributes = True


class SyncConnectionCreate(BaseModel):
    """Schema for creating a sync connection."""

    connection_id: UUID
    role: DestinationRole = DestinationRole.SHADOW


class SyncConnectionUpdate(BaseModel):
    """Schema for updating a sync connection."""

    role: Optional[DestinationRole] = None


class SyncConnection(SyncConnectionBase):
    """Schema for sync connection response."""

    id: UUID
    created_at: datetime
    modified_at: Optional[datetime] = None


class DestinationSlotInfo(BaseModel):
    """Info about a destination slot for the multiplexer."""

    slot_id: UUID = Field(..., description="Sync connection ID")
    destination_connection_id: UUID = Field(..., description="Connection ID of the destination")
    destination_name: str = Field(..., description="Name of the destination connection")
    destination_short_name: str = Field(..., description="Short name of the destination type")
    role: DestinationRole = Field(..., description="Current role (active/shadow/deprecated)")
    created_at: datetime = Field(..., description="When this slot was created")
    entity_count: int = Field(0, description="Entity count in ARF store")

    class Config:
        """Pydantic config."""

        from_attributes = True


class ForkDestinationRequest(BaseModel):
    """Request schema for forking a new destination."""

    destination_connection_id: UUID = Field(
        ..., description="ID of the destination connection to add"
    )
    replay_from_arf: bool = Field(
        False, description="Whether to auto-replay entities from ARF store"
    )


class SwitchDestinationResponse(BaseModel):
    """Response schema for switching active destination."""

    status: str = "switched"
    new_active_slot_id: UUID
    previous_active_slot_id: Optional[UUID] = None


class ForkDestinationResponse(BaseModel):
    """Response schema for forking a new destination."""

    slot: "SyncConnection"
    replay_job_id: Optional[UUID] = Field(
        None, description="Replay job ID if replay_from_arf was requested"
    )
    replay_job_status: Optional[str] = Field(None, description="Status of the replay job")
