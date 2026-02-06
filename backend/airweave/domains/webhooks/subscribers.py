"""Event subscribers for the webhooks domain."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from airweave.core.events.sync import SyncLifecycleEvent
    from airweave.core.protocols import WebhookPublisher
    from airweave.core.protocols.event_bus import DomainEvent

from airweave.core.events.sync import SyncEventType

logger = logging.getLogger(__name__)


class SyncEventSubscriber:
    """Publishes sync lifecycle events to external webhook endpoints.

    Subscribes to sync.* events and forwards them to registered webhooks.
    """

    EVENT_PATTERNS = ["sync.*"]

    # Map enum → status string for the webhook payload
    _STATUS_MAP: dict[SyncEventType, str] = {
        SyncEventType.PENDING: "pending",
        SyncEventType.RUNNING: "running",
        SyncEventType.COMPLETED: "completed",
        SyncEventType.FAILED: "failed",
        SyncEventType.CANCELLED: "cancelled",
    }

    def __init__(self, publisher: "WebhookPublisher") -> None:
        """Initialize with a webhook publisher.

        Args:
            publisher: Protocol for publishing sync events.
        """
        self._publisher = publisher

    async def handle(self, event: "DomainEvent") -> None:
        """Handle a sync lifecycle event.

        Args:
            event: The domain event (expected to be SyncLifecycleEvent).
        """
        if not event.event_type.startswith("sync."):
            return

        # Type narrow to SyncLifecycleEvent
        sync_event: "SyncLifecycleEvent" = event  # type: ignore[assignment]

        logger.debug(
            f"SyncEventSubscriber: handling {sync_event.event_type} "
            f"for sync_job {sync_event.sync_job_id}"
        )

        status = self._STATUS_MAP.get(sync_event.event_type)
        if status is None:
            logger.warning(f"SyncEventSubscriber: unknown event type {sync_event.event_type}")
            return

        await self._publisher.publish_sync_event(
            org_id=sync_event.organization_id,
            source_connection_id=sync_event.source_connection_id,
            sync_job_id=sync_event.sync_job_id,
            sync_id=sync_event.sync_id,
            collection_id=sync_event.collection_id,
            collection_name=sync_event.collection_name,
            collection_readable_id=sync_event.collection_readable_id,
            source_type=sync_event.source_type,
            status=status,
            error=sync_event.error,
        )
