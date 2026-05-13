"""Sync state machine — validates transitions, writes DB, manages Temporal schedules.

Single entry point for all sync status changes. Enforces the transition graph,
updates the DB with optimistic locking, and applies schedule side effects
(pause/unpause/delete) after commit.

Idempotent: re-writing the current status is a no-op (no DB write, no side effects).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from temporalio.service import RPCError

from airweave.core.context import BaseContext
from airweave.core.logging import logger
from airweave.core.shared_models import SyncPauseReason, SyncStatus
from airweave.db.session import get_db_context
from airweave.domains.syncs.protocols import SyncRepositoryProtocol, SyncStateMachineProtocol
from airweave.domains.syncs.types import (
    InvalidSyncTransitionError,
    SyncTransitionResult,
)
from airweave.domains.temporal.protocols import TemporalScheduleServiceProtocol

# ---------------------------------------------------------------------------
# Transition graph
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[SyncStatus, set[SyncStatus]] = {
    SyncStatus.ACTIVE: {SyncStatus.PAUSED, SyncStatus.INACTIVE},
    SyncStatus.PAUSED: {SyncStatus.ACTIVE},
    SyncStatus.INACTIVE: {SyncStatus.ACTIVE},
    SyncStatus.ERROR: {SyncStatus.ACTIVE, SyncStatus.PAUSED},
}


# ---------------------------------------------------------------------------
# State machine service
# ---------------------------------------------------------------------------


@dataclass
class SyncStateMachine(SyncStateMachineProtocol):
    """Validates sync transitions, writes to DB, manages Temporal schedules.

    Idempotent: if the sync is already in the target state, returns
    ``SyncTransitionResult(applied=False)`` without touching DB or schedules.

    Uses optimistic locking: the UPDATE only succeeds if the status hasn't
    changed between the read and write.

    Dependencies:
        sync_repo: Read current status + persist updates
        temporal_schedule_service: Pause/unpause Temporal schedules after commit
    """

    sync_repo: SyncRepositoryProtocol
    temporal_schedule_service: TemporalScheduleServiceProtocol

    async def transition(
        self,
        sync_id: UUID,
        target: SyncStatus,
        ctx: BaseContext,
        *,
        reason: str = "",
        pause_reason: SyncPauseReason | None = None,
    ) -> SyncTransitionResult:
        """Execute a validated, idempotent sync status transition.

        1. Read + validate inside a DB transaction.
        2. Conditional UPDATE with optimistic lock (WHERE status = current).
        3. Apply schedule side effects after the commit succeeds.
        """
        async with get_db_context() as db:
            sync_obj = await self.sync_repo.get_without_connections(db, sync_id, ctx)
            if not sync_obj:
                raise ValueError(f"Sync {sync_id} not found")

            current = SyncStatus(sync_obj.status)

            if current == target:
                logger.debug(f"Sync {sync_id} already in {target.value} (idempotent skip)")
                return SyncTransitionResult(applied=False, previous=current, current=current)

            self._validate_transition(current, target, sync_id)

            await self.sync_repo.transition_status(db, sync_id, current, target)
            if target == SyncStatus.PAUSED:
                sync_obj.pause_reason = pause_reason.value if pause_reason else None
            elif target == SyncStatus.ACTIVE:
                sync_obj.pause_reason = None
            await db.commit()

        logger.info(f"Sync {sync_id}: {current.value} → {target.value}")

        await self._apply_side_effects(sync_id, target, reason)

        return SyncTransitionResult(applied=True, previous=current, current=target)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_transition(
        current: SyncStatus,
        target: SyncStatus,
        sync_id: UUID | str | None = None,
    ) -> None:
        """Raise InvalidSyncTransitionError if the transition is not allowed."""
        allowed = _VALID_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise InvalidSyncTransitionError(current, target, sync_id)

    async def _apply_side_effects(
        self,
        sync_id: UUID,
        target: SyncStatus,
        reason: str,
    ) -> None:
        """Pause, unpause, or clean up Temporal schedules based on the target state."""
        try:
            if target == SyncStatus.PAUSED:
                await self.temporal_schedule_service.pause_schedules_for_sync(
                    sync_id, reason=reason or "Sync paused"
                )
            elif target == SyncStatus.ACTIVE:
                await self.temporal_schedule_service.unpause_schedules_for_sync(sync_id)
            elif target == SyncStatus.INACTIVE:
                await self.temporal_schedule_service.pause_schedules_for_sync(
                    sync_id, reason=reason or "Sync deactivated"
                )
        except (RPCError, OSError) as e:
            logger.warning(f"Schedule side effect failed for sync {sync_id}: {e}")
