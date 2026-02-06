"""Sync domain events.

These events are published during sync lifecycle transitions
and consumed by webhooks, analytics, realtime, etc.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID


class SyncEventType(str, Enum):
    """Strongly-typed sync event types.

    Extends str so it satisfies the DomainEvent.event_type protocol (str)
    and works transparently with fnmatch pattern matching in the event bus.
    """

    PENDING = "sync.pending"
    RUNNING = "sync.running"
    COMPLETED = "sync.completed"
    FAILED = "sync.failed"
    CANCELLED = "sync.cancelled"


@dataclass(frozen=True)
class SyncLifecycleEvent:
    """Event published during sync lifecycle transitions.

    Published when a sync job transitions to:
    - PENDING (job created)
    - RUNNING (execution started)
    - COMPLETED (success)
    - FAILED (error)
    - CANCELLED (user cancelled)

    Subscribers:
    - WebhookSubscriber: Sends to external webhook endpoints (Svix)
    - AnalyticsSubscriber: Tracks in PostHog
    - RealtimeSubscriber: Pushes to Redis PubSub for UI updates
    """

    # Event metadata
    event_type: SyncEventType
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Identifiers
    organization_id: UUID = field(default=None)  # type: ignore[assignment]
    sync_id: UUID = field(default=None)  # type: ignore[assignment]
    sync_job_id: UUID = field(default=None)  # type: ignore[assignment]
    collection_id: UUID = field(default=None)  # type: ignore[assignment]
    source_connection_id: UUID = field(default=None)  # type: ignore[assignment]

    # Context
    source_type: str = ""  # e.g., "slack", "notion"
    collection_name: str = ""
    collection_readable_id: str = ""

    # Metrics (for completed events)
    entities_inserted: int = 0
    entities_updated: int = 0
    entities_deleted: int = 0
    entities_skipped: int = 0
    chunks_written: int = 0

    # Error info (for failed events)
    error: Optional[str] = None

    @classmethod
    def pending(
        cls,
        organization_id: UUID,
        sync_id: UUID,
        sync_job_id: UUID,
        collection_id: UUID,
        source_connection_id: UUID,
        source_type: str,
        collection_name: str,
        collection_readable_id: str,
    ) -> "SyncLifecycleEvent":
        """Create a PENDING event (job created)."""
        return cls(
            event_type=SyncEventType.PENDING,
            organization_id=organization_id,
            sync_id=sync_id,
            sync_job_id=sync_job_id,
            collection_id=collection_id,
            source_connection_id=source_connection_id,
            source_type=source_type,
            collection_name=collection_name,
            collection_readable_id=collection_readable_id,
        )

    @classmethod
    def running(
        cls,
        organization_id: UUID,
        sync_id: UUID,
        sync_job_id: UUID,
        collection_id: UUID,
        source_connection_id: UUID,
        source_type: str,
        collection_name: str,
        collection_readable_id: str,
    ) -> "SyncLifecycleEvent":
        """Create a RUNNING event (execution started)."""
        return cls(
            event_type=SyncEventType.RUNNING,
            organization_id=organization_id,
            sync_id=sync_id,
            sync_job_id=sync_job_id,
            collection_id=collection_id,
            source_connection_id=source_connection_id,
            source_type=source_type,
            collection_name=collection_name,
            collection_readable_id=collection_readable_id,
        )

    @classmethod
    def completed(
        cls,
        organization_id: UUID,
        sync_id: UUID,
        sync_job_id: UUID,
        collection_id: UUID,
        source_connection_id: UUID,
        source_type: str,
        collection_name: str,
        collection_readable_id: str,
        entities_inserted: int = 0,
        entities_updated: int = 0,
        entities_deleted: int = 0,
        entities_skipped: int = 0,
        chunks_written: int = 0,
    ) -> "SyncLifecycleEvent":
        """Create a COMPLETED event (success)."""
        return cls(
            event_type=SyncEventType.COMPLETED,
            organization_id=organization_id,
            sync_id=sync_id,
            sync_job_id=sync_job_id,
            collection_id=collection_id,
            source_connection_id=source_connection_id,
            source_type=source_type,
            collection_name=collection_name,
            collection_readable_id=collection_readable_id,
            entities_inserted=entities_inserted,
            entities_updated=entities_updated,
            entities_deleted=entities_deleted,
            entities_skipped=entities_skipped,
            chunks_written=chunks_written,
        )

    @classmethod
    def failed(
        cls,
        organization_id: UUID,
        sync_id: UUID,
        sync_job_id: UUID,
        collection_id: UUID,
        source_connection_id: UUID,
        source_type: str,
        collection_name: str,
        collection_readable_id: str,
        error: str,
    ) -> "SyncLifecycleEvent":
        """Create a FAILED event (error)."""
        return cls(
            event_type=SyncEventType.FAILED,
            organization_id=organization_id,
            sync_id=sync_id,
            sync_job_id=sync_job_id,
            collection_id=collection_id,
            source_connection_id=source_connection_id,
            source_type=source_type,
            collection_name=collection_name,
            collection_readable_id=collection_readable_id,
            error=error,
        )

    @classmethod
    def cancelled(
        cls,
        organization_id: UUID,
        sync_id: UUID,
        sync_job_id: UUID,
        collection_id: UUID,
        source_connection_id: UUID,
        source_type: str,
        collection_name: str,
        collection_readable_id: str,
    ) -> "SyncLifecycleEvent":
        """Create a CANCELLED event (user cancelled)."""
        return cls(
            event_type=SyncEventType.CANCELLED,
            organization_id=organization_id,
            sync_id=sync_id,
            sync_job_id=sync_job_id,
            collection_id=collection_id,
            source_connection_id=source_connection_id,
            source_type=source_type,
            collection_name=collection_name,
            collection_readable_id=collection_readable_id,
        )
