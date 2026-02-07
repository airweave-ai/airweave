"""Webhook domain types.

Pure domain types with no infrastructure dependencies.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class EventType(str, Enum):
    """Webhook event types.

    All available event types that webhook subscribers can filter on.
    Convention: {domain}.{action} — matches the event_type string
    on the corresponding domain event class.
    """

    # Sync lifecycle
    SYNC_PENDING = "sync.pending"
    SYNC_RUNNING = "sync.running"
    SYNC_COMPLETED = "sync.completed"
    SYNC_FAILED = "sync.failed"
    SYNC_CANCELLED = "sync.cancelled"

    # Source connection lifecycle
    SOURCE_CONNECTION_CREATED = "source_connection.created"
    SOURCE_CONNECTION_AUTH_COMPLETED = "source_connection.auth_completed"
    SOURCE_CONNECTION_DELETED = "source_connection.deleted"

    # Collection lifecycle
    COLLECTION_CREATED = "collection.created"
    COLLECTION_UPDATED = "collection.updated"
    COLLECTION_DELETED = "collection.deleted"


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
