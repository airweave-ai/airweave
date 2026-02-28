"""Event type enums — the vocabulary of the event bus.

Every domain event must use one of these enums for its event_type field.
The union `EventType` constrains DomainEvent.event_type to known values.

When adding a new event domain:
1. Define its enum here
2. Add it to the EventType union
3. Add it to ALL_EVENT_TYPE_ENUMS (webhooks EventType is derived from it)
"""

from enum import Enum


class SyncEventType(str, Enum):
    """Sync lifecycle event types."""

    PENDING = "sync.pending"
    RUNNING = "sync.running"
    COMPLETED = "sync.completed"
    FAILED = "sync.failed"
    CANCELLED = "sync.cancelled"


class EntityEventType(str, Enum):
    """Entity-level operational event types (high-frequency, per-batch)."""

    BATCH_PROCESSED = "entity.batch_processed"


class QueryEventType(str, Enum):
    """Query-level event types (emitted after each search completes)."""

    PROCESSED = "query.processed"


class AccessControlEventType(str, Enum):
    """Access control event types."""

    BATCH_PROCESSED = "access_control.batch_processed"


class CollectionEventType(str, Enum):
    """Collection lifecycle event types."""

    CREATED = "collection.created"
    UPDATED = "collection.updated"
    DELETED = "collection.deleted"


class SourceConnectionEventType(str, Enum):
    """Source connection lifecycle event types."""

    CREATED = "source_connection.created"
    AUTH_COMPLETED = "source_connection.auth_completed"
    DELETED = "source_connection.deleted"


# Union of all known event types.
# DomainEvent.event_type is typed to this, ensuring only known values are used.
EventType = (
    SyncEventType
    | EntityEventType
    | QueryEventType
    | AccessControlEventType
    | CollectionEventType
    | SourceConnectionEventType
)

# Ordered tuple of every event-type enum class.
# Used by domains/webhooks/types.py to derive its EventType enum automatically.
ALL_EVENT_TYPE_ENUMS: tuple[type[Enum], ...] = (
    SyncEventType,
    EntityEventType,
    QueryEventType,
    AccessControlEventType,
    CollectionEventType,
    SourceConnectionEventType,
)
