"""Webhook domain types.

Pure domain types with no infrastructure dependencies.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID


class EventType(str, Enum):
    """Webhook event types."""

    SYNC_PENDING = "sync.pending"
    SYNC_RUNNING = "sync.running"
    SYNC_COMPLETED = "sync.completed"
    SYNC_FAILED = "sync.failed"
    SYNC_CANCELLED = "sync.cancelled"


# ---------------------------------------------------------------------------
# Domain types for webhook subscriptions and messages
# ---------------------------------------------------------------------------


@dataclass
class Subscription:
    """A webhook subscription (endpoint)."""

    id: str
    url: str
    event_types: list[str]
    disabled: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Optional fields populated on detail views
    secret: Optional[str] = None
    delivery_attempts: list["DeliveryAttempt"] = field(default_factory=list)


@dataclass
class EventMessage:
    """A webhook event message."""

    id: str
    event_type: str
    payload: dict
    timestamp: datetime
    channels: list[str] = field(default_factory=list)


@dataclass
class DeliveryAttempt:
    """A delivery attempt for a webhook message."""

    id: str
    message_id: str
    endpoint_id: str
    timestamp: datetime
    response_status_code: int
    response: Optional[str] = None
    url: Optional[str] = None


@dataclass
class RecoveryTask:
    """A message recovery task."""

    id: str
    status: str  # "running", "completed", "unknown"


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------


class WebhooksError(Exception):
    """Error from webhook operations."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        """Initialize with message and optional HTTP status code."""
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Event payload for publishing
# ---------------------------------------------------------------------------


@dataclass
class SyncEventPayload:
    """Payload for sync lifecycle webhook events."""

    event_type: EventType
    job_id: UUID
    collection_readable_id: str
    collection_name: str
    source_type: str
    status: str  # SyncJobStatus value
    timestamp: datetime
    source_connection_id: Optional[UUID] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dict for webhook payload."""
        return {
            "event_type": self.event_type.value,
            "job_id": str(self.job_id),
            "collection_readable_id": self.collection_readable_id,
            "collection_name": self.collection_name,
            "source_connection_id": str(self.source_connection_id)
            if self.source_connection_id
            else None,
            "source_type": self.source_type,
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def event_type_from_status(status: str) -> Optional[EventType]:
    """Convert a sync job status string to EventType."""
    mapping = {
        "pending": EventType.SYNC_PENDING,
        "running": EventType.SYNC_RUNNING,
        "completed": EventType.SYNC_COMPLETED,
        "failed": EventType.SYNC_FAILED,
        "cancelled": EventType.SYNC_CANCELLED,
    }
    return mapping.get(status.lower())
