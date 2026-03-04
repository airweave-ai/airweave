"""Event bus subscriber that forwards domain events to analytics."""

import logging
from typing import Callable, Dict, Union

from airweave.adapters.analytics.protocols import AnalyticsTrackerProtocol
from airweave.core.events.collection import CollectionLifecycleEvent
from airweave.core.events.source_connection import SourceConnectionLifecycleEvent
from airweave.core.events.sync import SyncLifecycleEvent
from airweave.core.protocols.event_bus import EventSubscriber

logger = logging.getLogger(__name__)

_Event = Union[CollectionLifecycleEvent, SourceConnectionLifecycleEvent, SyncLifecycleEvent]


class AnalyticsEventSubscriber(EventSubscriber):
    """Maps domain events to PostHog analytics calls.

    Registered on the event bus at startup. Each ``_handle_*`` method
    converts one event type into its analytics shape. Adding a new
    tracked event = one new method + one entry in ``_handlers``.
    """

    EVENT_PATTERNS = [
        "collection.*",
        "source_connection.*",
        "sync.*",
    ]

    def __init__(self, tracker: AnalyticsTrackerProtocol) -> None:
        """Wire handler dispatch table to the given tracker."""
        self._tracker = tracker
        self._handlers: Dict[str, Callable[[_Event], None]] = {
            "source_connection.created": self._handle_sc_created,
            "source_connection.auth_completed": self._handle_sc_auth_completed,
            "source_connection.deleted": self._handle_sc_deleted,
            "collection.created": self._handle_collection_created,
            "collection.updated": self._handle_collection_updated,
            "collection.deleted": self._handle_collection_deleted,
            "sync.completed": self._handle_sync_completed,
            "sync.failed": self._handle_sync_failed,
            "sync.cancelled": self._handle_sync_cancelled,
        }

    async def handle(self, event: _Event) -> None:
        """Dispatch a domain event to the appropriate handler."""
        event_type_value: str = event.event_type.value
        handler = self._handlers.get(event_type_value)
        if handler is None:
            return
        try:
            handler(event)
        except Exception as e:
            logger.error(
                "AnalyticsEventSubscriber failed for '%s': %s",
                event_type_value,
                e,
            )

    # ------------------------------------------------------------------
    # Collection events
    # ------------------------------------------------------------------

    def _handle_collection_created(self, event: CollectionLifecycleEvent) -> None:
        self._tracker.track(
            event_name="collection_created",
            distinct_id=str(event.organization_id),
            properties={
                "collection_id": str(event.collection_id),
                "collection_name": event.collection_name,
                "collection_readable_id": event.collection_readable_id,
            },
            groups={"organization": str(event.organization_id)},
        )

    def _handle_collection_updated(self, event: CollectionLifecycleEvent) -> None:
        self._tracker.track(
            event_name="collection_updated",
            distinct_id=str(event.organization_id),
            properties={
                "collection_id": str(event.collection_id),
                "collection_name": event.collection_name,
                "collection_readable_id": event.collection_readable_id,
            },
            groups={"organization": str(event.organization_id)},
        )

    def _handle_collection_deleted(self, event: CollectionLifecycleEvent) -> None:
        self._tracker.track(
            event_name="collection_deleted",
            distinct_id=str(event.organization_id),
            properties={
                "collection_id": str(event.collection_id),
                "collection_name": event.collection_name,
                "collection_readable_id": event.collection_readable_id,
            },
            groups={"organization": str(event.organization_id)},
        )

    # ------------------------------------------------------------------
    # Source connection events
    # ------------------------------------------------------------------

    def _handle_sc_created(self, event: SourceConnectionLifecycleEvent) -> None:
        self._tracker.track(
            event_name="source_connection_created",
            distinct_id=str(event.organization_id),
            properties={
                "connection_id": str(event.source_connection_id),
                "source_type": event.source_type,
                "collection_readable_id": event.collection_readable_id,
                "is_authenticated": event.is_authenticated,
            },
            groups={"organization": str(event.organization_id)},
        )

    def _handle_sc_auth_completed(self, event: SourceConnectionLifecycleEvent) -> None:
        self._tracker.track(
            event_name="source_connection_auth_completed",
            distinct_id=str(event.organization_id),
            properties={
                "connection_id": str(event.source_connection_id),
                "source_type": event.source_type,
            },
            groups={"organization": str(event.organization_id)},
        )

    def _handle_sc_deleted(self, event: SourceConnectionLifecycleEvent) -> None:
        self._tracker.track(
            event_name="source_connection_deleted",
            distinct_id=str(event.organization_id),
            properties={
                "connection_id": str(event.source_connection_id),
                "source_type": event.source_type,
            },
            groups={"organization": str(event.organization_id)},
        )

    # ------------------------------------------------------------------
    # Sync events
    # ------------------------------------------------------------------

    def _handle_sync_completed(self, event: SyncLifecycleEvent) -> None:
        self._tracker.track(
            event_name="sync_completed",
            distinct_id=str(event.organization_id),
            properties={
                "sync_id": str(event.sync_id),
                "sync_job_id": str(event.sync_job_id),
                "source_type": event.source_type,
                "collection_readable_id": event.collection_readable_id,
                "entities_inserted": event.entities_inserted,
                "entities_updated": event.entities_updated,
                "entities_deleted": event.entities_deleted,
                "entities_skipped": event.entities_skipped,
                "entities_synced": event.entities_inserted + event.entities_updated,
                "chunks_written": event.chunks_written,
            },
            groups={"organization": str(event.organization_id)},
        )

    def _handle_sync_failed(self, event: SyncLifecycleEvent) -> None:
        self._tracker.track(
            event_name="sync_failed",
            distinct_id=str(event.organization_id),
            properties={
                "sync_id": str(event.sync_id),
                "sync_job_id": str(event.sync_job_id),
                "source_type": event.source_type,
                "error": event.error or "",
            },
            groups={"organization": str(event.organization_id)},
        )

    def _handle_sync_cancelled(self, event: SyncLifecycleEvent) -> None:
        self._tracker.track(
            event_name="sync_cancelled",
            distinct_id=str(event.organization_id),
            properties={
                "sync_id": str(event.sync_id),
                "sync_job_id": str(event.sync_job_id),
                "source_type": event.source_type,
                "source_connection_id": str(event.source_connection_id),
            },
            groups={"organization": str(event.organization_id)},
        )
