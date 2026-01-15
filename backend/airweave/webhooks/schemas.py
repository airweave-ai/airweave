"""Webhook event payload schemas.

This module defines Pydantic schemas for webhook event payloads sent to subscribers.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from airweave.core.shared_models import SyncJobStatus
from airweave.webhooks.constants.event_types import EventType


class SyncEventPayload(BaseModel):
    """Payload for sync-related webhook events.

    This schema defines the data sent to webhook subscribers when sync events occur
    (e.g., sync.pending, sync.running, sync.completed, sync.failed, sync.cancelled).
    """

    event_type: EventType = Field(
        ...,
        description="The type of sync event",
    )

    # Job identifier
    job_id: UUID = Field(
        ...,
        description="Unique identifier for this sync job",
    )

    # Collection info
    collection_readable_id: str = Field(
        ...,
        description="Human-readable identifier for the collection (e.g., 'finance-data-ab123')",
    )
    collection_name: str = Field(
        ...,
        description="Display name of the collection",
    )

    # Source info
    source_connection_id: Optional[UUID] = Field(
        None,
        description="Unique identifier for the source connection",
    )
    source_type: str = Field(
        ...,
        description="Short name of the source type (e.g., 'slack', 'notion', 'github')",
    )

    # Status info
    status: SyncJobStatus = Field(
        ...,
        description="Current status of the sync job",
    )
    timestamp: datetime = Field(
        ...,
        description="When this event occurred (ISO 8601 format)",
    )

    # Error info (only for failed events)
    error: Optional[str] = Field(
        None,
        description="Error message if the sync failed",
    )

    class Config:
        """Pydantic config."""

        from_attributes = True
        use_enum_values = True
        json_schema_extra = {
            "examples": [
                {
                    "event_type": "sync.completed",
                    "job_id": "550e8400-e29b-41d4-a716-446655440000",
                    "collection_readable_id": "finance-data-ab123",
                    "collection_name": "Finance Data",
                    "source_connection_id": "880e8400-e29b-41d4-a716-446655440003",
                    "source_type": "slack",
                    "status": "completed",
                    "timestamp": "2024-01-15T14:22:15Z",
                },
                {
                    "event_type": "sync.failed",
                    "job_id": "550e8400-e29b-41d4-a716-446655440000",
                    "collection_readable_id": "finance-data-ab123",
                    "collection_name": "Finance Data",
                    "source_type": "notion",
                    "status": "failed",
                    "timestamp": "2024-01-15T14:22:15Z",
                    "error": "Authentication token expired",
                },
            ]
        }
