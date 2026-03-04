"""Usage billing listener — EventBus subscriber for all billable events."""

import logging
from typing import List

from airweave.core.events.base import DomainEvent
from airweave.core.events.enums import SourceConnectionEventType
from airweave.core.events.source_connection import SourceConnectionLifecycleEvent
from airweave.core.events.sync import (
    EntityBatchProcessedEvent,
    QueryProcessedEvent,
    SyncLifecycleEvent,
)
from airweave.core.protocols.event_bus import EventSubscriber
from airweave.domains.usage.protocols import UsageLedgerProtocol
from airweave.domains.usage.types import ActionType

logger = logging.getLogger(__name__)


class UsageBillingListener(EventSubscriber):
    """Stateless fan-in subscriber that routes billable events to the UsageLedger.

    Subscribes to entity.*, query.*, sync.*, and source_connection.* patterns. Each event is
    mapped to a ``ledger.record()`` call.  Terminal sync events trigger
    a ``ledger.flush()`` for the org to ensure nothing is left pending.
    """

    EVENT_PATTERNS: List[str] = ["entity.*", "query.*", "sync.*", "source_connection.*"]

    _TERMINAL_SYNC_TYPES = frozenset({"sync.completed", "sync.failed", "sync.cancelled"})

    def __init__(self, ledger: UsageLedgerProtocol) -> None:
        """Initialize with the usage ledger to record events."""
        self._ledger = ledger

    async def handle(self, event: DomainEvent) -> None:
        """Route billable domain events to the ledger."""
        try:
            if isinstance(event, EntityBatchProcessedEvent):
                await self._handle_entity_batch(event)
            elif isinstance(event, QueryProcessedEvent):
                await self._handle_query(event)
            elif isinstance(event, SyncLifecycleEvent):
                await self._handle_sync_lifecycle(event)
            elif isinstance(event, SourceConnectionLifecycleEvent):
                await self._handle_source_connection_lifecycle(event)
        except Exception as e:
            logger.error(
                "UsageBillingListener failed for org %s: %s",
                event.organization_id,
                e,
                exc_info=True,
            )

    async def _handle_entity_batch(self, event: EntityBatchProcessedEvent) -> None:
        if not event.billable:
            return

        total_synced = event.inserted + event.updated
        if total_synced <= 0:
            return

        await self._ledger.record(event.organization_id, ActionType.ENTITIES, amount=total_synced)

    async def _handle_query(self, event: QueryProcessedEvent) -> None:
        if not event.billable:
            return

        await self._ledger.record(event.organization_id, ActionType.QUERIES, amount=event.queries)

    async def _handle_sync_lifecycle(self, event: SyncLifecycleEvent) -> None:
        if event.event_type.value in self._TERMINAL_SYNC_TYPES:
            await self._ledger.flush(event.organization_id)

    async def _handle_source_connection_lifecycle(
        self, event: SourceConnectionLifecycleEvent
    ) -> None:
        if event.event_type == SourceConnectionEventType.CREATED:
            await self._ledger.record(
                event.organization_id,
                ActionType.SOURCE_CONNECTIONS,
                amount=1,
            )
        elif event.event_type == SourceConnectionEventType.DELETED:
            await self._ledger.record(
                event.organization_id,
                ActionType.SOURCE_CONNECTIONS,
                amount=-1,
            )
