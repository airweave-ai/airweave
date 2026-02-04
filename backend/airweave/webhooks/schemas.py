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
        json_schema_extra={"example": "sync.completed"},
    )
    job_id: UUID = Field(
        ...,
        description="Unique identifier for this sync job",
        json_schema_extra={"example": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"},
    )
    collection_readable_id: str = Field(
        ...,
        description="Human-readable identifier for the collection (e.g., 'finance-data-ab123')",
        json_schema_extra={"example": "customer-support-tickets-x7k9m"},
    )
    collection_name: str = Field(
        ...,
        description="Display name of the collection",
        json_schema_extra={"example": "Customer Support Tickets"},
    )
    source_connection_id: Optional[UUID] = Field(
        None,
        description="Unique identifier for the source connection",
        json_schema_extra={"example": "b2c3d4e5-f6a7-8901-bcde-f23456789012"},
    )
    source_type: str = Field(
        ...,
        description="Short name of the source type (e.g., 'hubspot', 'notion', 'salesforce')",
        json_schema_extra={"example": "hubspot"},
    )
    status: SyncJobStatus = Field(
        ...,
        description="Current status of the sync job",
        json_schema_extra={"example": "completed"},
    )
    timestamp: datetime = Field(
        ...,
        description="When this event occurred (ISO 8601 format, UTC)",
        json_schema_extra={"example": "2024-03-15T09:45:32Z"},
    )
    error: Optional[str] = Field(
        None,
        description="Error message if the sync failed (only present for failed events)",
        json_schema_extra={"example": None},
    )

    model_config = {
        "from_attributes": True,
        "use_enum_values": True,
        "json_schema_extra": {
            "examples": [
                {
                    "summary": "Sync Completed",
                    "description": "A successful sync job completion event",
                    "value": {
                        "event_type": "sync.completed",
                        "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        "collection_readable_id": "customer-support-tickets-x7k9m",
                        "collection_name": "Customer Support Tickets",
                        "source_connection_id": "b2c3d4e5-f6a7-8901-bcde-f23456789012",
                        "source_type": "zendesk",
                        "status": "completed",
                        "timestamp": "2024-03-15T09:45:32Z",
                        "error": None,
                    },
                },
                {
                    "summary": "Sync Failed",
                    "description": "A failed sync job with error details",
                    "value": {
                        "event_type": "sync.failed",
                        "job_id": "c3d4e5f6-a7b8-9012-cdef-345678901234",
                        "collection_readable_id": "sales-pipeline-data-p4q8r",
                        "collection_name": "Sales Pipeline Data",
                        "source_connection_id": "d4e5f6a7-b8c9-0123-def0-456789012345",
                        "source_type": "salesforce",
                        "status": "failed",
                        "timestamp": "2024-03-15T10:12:05Z",
                        "error": "Authentication failed: OAuth token expired. "
                        "Please reconnect the source.",
                    },
                },
                {
                    "summary": "Sync Pending",
                    "description": "A sync job queued for execution",
                    "value": {
                        "event_type": "sync.pending",
                        "job_id": "e5f6a7b8-c9d0-1234-ef01-567890123456",
                        "collection_readable_id": "engineering-docs-m2n5p",
                        "collection_name": "Engineering Documentation",
                        "source_connection_id": "f6a7b8c9-d0e1-2345-f012-678901234567",
                        "source_type": "confluence",
                        "status": "pending",
                        "timestamp": "2024-03-15T08:30:00Z",
                        "error": None,
                    },
                },
            ],
        },
    }
