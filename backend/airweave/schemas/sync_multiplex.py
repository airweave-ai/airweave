"""Schemas for sync multiplexer (destination migrations)."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from airweave.models.sync_connection import DestinationRole


class DestinationSlotInfo(BaseModel):
    """Info about a destination slot."""

    slot_id: UUID
    connection_id: UUID
    connection_name: str
    role: DestinationRole
    created_at: datetime

    class Config:
        from_attributes = True


class ForkDestinationRequest(BaseModel):
    """Request to fork a new shadow destination."""

    destination_connection_id: UUID = Field(..., description="Connection ID to add as shadow")
    replay_from_arf: bool = Field(False, description="Whether to replay entities from ARF")


class ForkDestinationResponse(BaseModel):
    """Response from fork operation."""

    slot_id: UUID
    replay_job_id: Optional[UUID] = None
