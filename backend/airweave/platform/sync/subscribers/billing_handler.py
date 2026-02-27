"""Billing handler — stateless subscriber that increments usage from batch events.

Subscribes to ``entity.*`` on the global EventBus. Looks up the usage
service per-organization from the usage_service_factory on each event.
Skips non-billable events (set by the pipeline when guardrails are disabled).
"""

import logging
from typing import TYPE_CHECKING

from airweave.core.events.base import DomainEvent
from airweave.core.events.sync import EntityBatchProcessedEvent
from airweave.core.protocols.event_bus import EventSubscriber
from airweave.db.session import get_db_context
from airweave.domains.usage.types import ActionType

if TYPE_CHECKING:
    from airweave.domains.usage.protocols import UsageServiceFactoryProtocol

logger = logging.getLogger(__name__)


class SyncBillingHandler(EventSubscriber):
    """Stateless EventBus subscriber for billing usage tracking.

    No per-sync registration needed. The event carries ``billable`` and
    ``organization_id`` — the handler looks up the usage service from the
    factory and increments.
    """

    EVENT_PATTERNS = ["entity.*"]

    def __init__(self, usage_service_factory: "UsageServiceFactoryProtocol") -> None:
        self._usage_factory = usage_service_factory

    async def handle(self, event: DomainEvent) -> None:
        if not isinstance(event, EntityBatchProcessedEvent):
            return

        if not event.billable:
            return

        total_synced = event.inserted + event.updated
        if total_synced <= 0:
            return

        try:
            usage_svc = self._usage_factory.create(
                organization_id=event.organization_id,
                logger=logger,
            )
            async with get_db_context() as db:
                await usage_svc.increment(db, ActionType.ENTITIES, amount=total_synced)
        except Exception as e:
            logger.error(
                f"Billing increment failed for org {event.organization_id}: {e}",
                exc_info=True,
            )
