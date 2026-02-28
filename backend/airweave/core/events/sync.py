"""Domain events for sync, entity batches, and queries.

EntityBatchProcessedEvent is emitted per resolved batch during sync
and consumed by the billing accumulator, progress relay, and (future) delta lake writers.

QueryProcessedEvent is emitted after a search completes and consumed
by the billing accumulator for query usage tracking.
"""

from typing import Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from airweave.core.events.base import DomainEvent
from airweave.core.events.enums import (
    AccessControlEventType,
    EntityEventType,
    QueryEventType,
    SyncEventType,
)


class TypeActionCounts(BaseModel):
    """Action counts for a single entity type within a batch."""

    model_config = ConfigDict(frozen=True)

    inserted: int = 0
    updated: int = 0
    deleted: int = 0
    kept: int = 0


class EntityBatchProcessedEvent(DomainEvent):
    """Emitted after each entity batch is resolved and dispatched.

    Carries per-type deltas for this batch. Running totals are derived
    by consumers (progress relay, billing), not embedded in the event.

    Consumers:
    - SyncProgressRelay: Accumulates deltas, publishes snapshots to Redis PubSub
    - UsageBillingListener: Accumulates usage (inserted + updated)
    - (future) Delta lake writer: Appends raw event as-is
    """

    event_type: EntityEventType = EntityEventType.BATCH_PROCESSED

    sync_id: UUID
    sync_job_id: UUID
    collection_id: UUID
    source_connection_id: UUID
    source_type: str = ""

    inserted: int = 0
    updated: int = 0
    deleted: int = 0
    kept: int = 0

    type_breakdown: Dict[str, TypeActionCounts] = Field(default_factory=dict)

    batch_seq: int = 0
    batch_duration_ms: float = 0
    billable: bool = True


class AccessControlMembershipBatchProcessedEvent(DomainEvent):
    """Emitted during ACL membership collection to signal progress.

    Unlike EntityBatchProcessedEvent (which tracks resolved entity actions),
    this tracks raw membership collection: how many memberships have been
    collected and written to DB so far.
    """

    event_type: AccessControlEventType = AccessControlEventType.BATCH_PROCESSED

    sync_id: UUID
    sync_job_id: UUID
    source_connection_id: UUID
    source_type: str = ""

    collected: int = 0
    upserted: int = 0


class QueryProcessedEvent(DomainEvent):
    """Emitted after a search (or agentic search) completes.

    Consumed by UsageBillingListener to record query usage.
    """

    event_type: QueryEventType = QueryEventType.PROCESSED

    collection_id: Optional[UUID] = None
    queries: int = 1
    billable: bool = True


class SyncLifecycleEvent(DomainEvent):
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

    event_type: SyncEventType

    # Identifiers
    sync_id: UUID
    sync_job_id: UUID
    collection_id: UUID
    source_connection_id: UUID

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
