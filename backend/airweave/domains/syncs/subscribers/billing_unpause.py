"""Unpause usage-exhausted syncs when a new billing period is created."""

from typing import ClassVar, Tuple

from airweave.core.context import SystemContext
from airweave.core.events.base import DomainEvent
from airweave.core.events.billing import BillingPeriodCreatedEvent
from airweave.core.logging import logger
from airweave.core.protocols.event_bus import EventSubscriber
from airweave.core.shared_models import SyncPauseReason
from airweave.db.session import get_db_context
from airweave.domains.organizations.protocols import OrganizationRepositoryProtocol
from airweave.domains.syncs.protocols import SyncServiceProtocol
from airweave.schemas.billing_period import BillingPeriodStatus


class BillingUnpauseSubscriber(EventSubscriber):
    """Unpause usage-exhausted syncs when a new active billing period is created."""

    EVENT_PATTERNS: ClassVar[Tuple[str, ...]] = ("billing.period_created",)

    def __init__(
        self,
        sync_service: SyncServiceProtocol,
        org_repo: OrganizationRepositoryProtocol,
    ) -> None:
        """Initialize with sync service and org repo."""
        self._sync_service = sync_service
        self._org_repo = org_repo

    async def handle(self, event: DomainEvent) -> None:
        """Handle billing period created events by unpausing usage-exhausted syncs."""
        if not isinstance(event, BillingPeriodCreatedEvent):
            return

        if event.status != BillingPeriodStatus.ACTIVE.value:
            return

        async with get_db_context() as db:
            org_schema = await self._org_repo.get(
                db, id=event.organization_id, skip_access_validation=True
            )
        if not org_schema:
            logger.warning(f"Org {event.organization_id} not found for billing unpause")
            return

        ctx = SystemContext(org_schema)

        paused_syncs = await self._sync_service.list_paused_by_reason(
            organization_id=event.organization_id,
            pause_reason=SyncPauseReason.USAGE_EXHAUSTED,
            ctx=ctx,
        )

        if not paused_syncs:
            return

        for sync in paused_syncs:
            try:
                await self._sync_service.resume(
                    sync.id,
                    ctx,
                    reason="Unpaused: new billing period",
                )
                logger.info(f"Unpaused sync {sync.id} after billing period reset")
            except Exception as e:
                logger.warning(f"Failed to unpause sync {sync.id}: {e}")
