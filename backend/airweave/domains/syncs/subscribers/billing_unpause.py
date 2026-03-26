"""Unpause usage-exhausted syncs when a new billing period is created."""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from sqlalchemy import select

from airweave import schemas
from airweave.core.context import SystemContext
from airweave.core.events.base import DomainEvent
from airweave.core.events.billing import BillingPeriodCreatedEvent
from airweave.core.logging import logger
from airweave.core.shared_models import SyncPauseReason, SyncStatus
from airweave.db.session import get_db_context
from airweave.models.organization import Organization
from airweave.models.sync import Sync
from airweave.schemas.billing_period import BillingPeriodStatus

if TYPE_CHECKING:
    from airweave.core.protocols.event_bus import EventSubscriber
    from airweave.domains.syncs.protocols import SyncStateMachineProtocol


class BillingUnpauseSubscriber:
    """Unpause usage-exhausted syncs when a new active billing period is created."""

    EVENT_PATTERNS: List[str] = ["billing.period_created"]

    def __init__(self, sync_state_machine: SyncStateMachineProtocol) -> None:
        self._sync_state_machine = sync_state_machine

    async def handle(self, event: DomainEvent) -> None:
        if not isinstance(event, BillingPeriodCreatedEvent):
            return

        if event.status != BillingPeriodStatus.ACTIVE.value:
            return

        async with get_db_context() as db:
            # Fetch org for SystemContext
            org = await db.get(Organization, event.organization_id)
            if not org:
                logger.warning(f"Org {event.organization_id} not found for billing unpause")
                return
            org_schema = schemas.Organization.model_validate(org, from_attributes=True)

            # Find paused syncs with usage_exhausted reason
            stmt = select(Sync).where(
                Sync.organization_id == event.organization_id,
                Sync.status == SyncStatus.PAUSED.value,
                Sync.pause_reason == SyncPauseReason.USAGE_EXHAUSTED.value,
            )
            result = await db.execute(stmt)
            paused_syncs = result.scalars().all()

        if not paused_syncs:
            return

        ctx = SystemContext(org_schema)

        for sync in paused_syncs:
            try:
                await self._sync_state_machine.transition(
                    sync_id=sync.id,
                    target=SyncStatus.ACTIVE,
                    ctx=ctx,
                    reason="Unpaused: new billing period",
                )
                logger.info(f"Unpaused sync {sync.id} after billing period reset")
            except Exception as e:
                logger.warning(f"Failed to unpause sync {sync.id}: {e}")
