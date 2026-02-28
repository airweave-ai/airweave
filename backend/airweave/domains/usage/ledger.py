"""Usage ledger — singleton write service that accumulates and flushes usage.

One instance lives in the container. Callers just call ``record()`` with
an org ID and action type; the ledger batches increments in memory and
flushes to the database when a threshold is crossed, or when ``flush()``
is called explicitly (e.g. at sync completion or app shutdown).
"""

import asyncio
import logging
from typing import Optional
from uuid import UUID

from airweave.domains.billing.repository import (
    BillingPeriodRepositoryProtocol,
    OrganizationBillingRepositoryProtocol,
)
from airweave.domains.usage.protocols import UsageLedgerProtocol
from airweave.domains.usage.repository import UsageRepositoryProtocol
from airweave.domains.usage.types import ActionType

logger = logging.getLogger(__name__)

_FLUSH_THRESHOLDS: dict[ActionType, int] = {
    ActionType.ENTITIES: 100,
    ActionType.QUERIES: 10,
}


class UsageLedger(UsageLedgerProtocol):
    """In-memory accumulator with threshold-based and time-based flushing.

    Thread-safe via per-org locks.  Owns its own DB sessions through
    ``get_db_context`` so callers never pass a session.

    A background task flushes all pending accumulators every
    ``flush_interval_seconds``.  The task is started lazily on the
    first ``record()`` call so no external wiring is needed.
    """

    def __init__(
        self,
        usage_repo: UsageRepositoryProtocol,
        billing_repo: OrganizationBillingRepositoryProtocol,
        period_repo: BillingPeriodRepositoryProtocol,
        flush_interval_seconds: float = 30.0,
    ) -> None:
        """Initialize the ledger with repository dependencies."""
        self._usage_repo = usage_repo
        self._billing_repo = billing_repo
        self._period_repo = period_repo
        self._flush_interval = flush_interval_seconds

        # org_id → { ActionType → pending_count }
        self._accumulators: dict[UUID, dict[ActionType, int]] = {}
        self._locks: dict[UUID, asyncio.Lock] = {}
        self._billing_cache: dict[UUID, bool] = {}
        self._flush_task: Optional[asyncio.Task] = None

    def _get_lock(self, organization_id: UUID) -> asyncio.Lock:
        if organization_id not in self._locks:
            self._locks[organization_id] = asyncio.Lock()
        return self._locks[organization_id]

    async def record(
        self,
        organization_id: UUID,
        action_type: ActionType,
        amount: int = 1,
    ) -> None:
        """Record usage increment for an organization and action type."""
        if action_type in (ActionType.TEAM_MEMBERS, ActionType.SOURCE_CONNECTIONS):
            return

        self._ensure_flush_task()

        lock = self._get_lock(organization_id)
        async with lock:
            if not await self._has_billing(organization_id):
                return

            acc = self._accumulators.setdefault(organization_id, {})
            acc[action_type] = acc.get(action_type, 0) + amount

            threshold = _FLUSH_THRESHOLDS.get(action_type, 10)
            if abs(acc[action_type]) >= threshold:
                await self._flush_action(organization_id, action_type)

    async def flush(self, organization_id: Optional[UUID] = None) -> None:
        """Flush pending usage to the database for one org or all orgs."""
        if organization_id is not None:
            lock = self._get_lock(organization_id)
            async with lock:
                await self._flush_org(organization_id)
        else:
            org_ids = list(self._accumulators.keys())
            for oid in org_ids:
                lock = self._get_lock(oid)
                async with lock:
                    await self._flush_org(oid)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_flush_task(self) -> None:
        """Lazily start the periodic flush background task."""
        if self._flush_task is not None and not self._flush_task.done():
            return
        self._flush_task = asyncio.create_task(self._periodic_flush_loop())
        logger.info("UsageLedger periodic flush started (interval=%ss)", self._flush_interval)

    async def _periodic_flush_loop(self) -> None:
        """Background loop that flushes all pending accumulators periodically.

        On cancellation (e.g. event-loop shutdown) does a final flush
        so no pending counts are lost.
        """
        try:
            while True:
                await asyncio.sleep(self._flush_interval)
                try:
                    await self.flush()
                except Exception:
                    logger.error("Periodic usage flush failed", exc_info=True)
        except asyncio.CancelledError:
            try:
                await self.flush()
                logger.info("UsageLedger final flush complete on shutdown")
            except Exception:
                logger.error("UsageLedger final flush failed on shutdown", exc_info=True)
            raise

    async def _has_billing(self, organization_id: UUID) -> bool:
        if organization_id in self._billing_cache:
            return self._billing_cache[organization_id]

        from airweave.db.session import get_db_context

        async with get_db_context() as db:
            record = await self._billing_repo.get_by_org_id(db, organization_id=organization_id)
        result = record is not None
        self._billing_cache[organization_id] = result
        return result

    async def _flush_action(self, organization_id: UUID, action_type: ActionType) -> None:
        """Flush a single action type for one org. Must be called under lock."""
        acc = self._accumulators.get(organization_id, {})
        pending = acc.get(action_type, 0)
        if pending == 0:
            return

        from airweave.db.session import get_db_context

        try:
            async with get_db_context() as db:
                await self._usage_repo.increment_usage(
                    db,
                    organization_id=organization_id,
                    increments={action_type: pending},
                )
            acc[action_type] = 0
            logger.debug("Flushed %s=%d for org %s", action_type.value, pending, organization_id)
        except Exception:
            logger.error(
                "Failed to flush %s=%d for org %s",
                action_type.value,
                pending,
                organization_id,
                exc_info=True,
            )

    async def _flush_org(self, organization_id: UUID) -> None:
        """Flush all pending action types for one org. Must be called under lock."""
        acc = self._accumulators.get(organization_id, {})
        to_flush = {at: count for at, count in acc.items() if count != 0}
        if not to_flush:
            return

        from airweave.db.session import get_db_context

        try:
            async with get_db_context() as db:
                await self._usage_repo.increment_usage(
                    db,
                    organization_id=organization_id,
                    increments=to_flush,
                )
            for at in to_flush:
                acc[at] = 0
            logger.info("Flushed usage for org %s: %s", organization_id, to_flush)
        except Exception:
            logger.error(
                "Failed to flush usage for org %s: %s",
                organization_id,
                to_flush,
                exc_info=True,
            )


class NullUsageLedger(UsageLedgerProtocol):
    """No-op ledger for local development / tests."""

    async def record(
        self,
        organization_id: UUID,
        action_type: ActionType,
        amount: int = 1,
    ) -> None:
        """No-op record."""
        pass

    async def flush(self, organization_id: Optional[UUID] = None) -> None:
        """No-op flush."""
        pass
