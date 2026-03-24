"""Sync job state machine — validates transitions, writes DB, publishes lifecycle events.

Single entry point for all sync job status changes. Enforces the transition graph,
derives timestamps from the target status, and publishes lifecycle events atomically.

Idempotent: re-writing the current status is a no-op (no DB write, no event).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from airweave.core.context import BaseContext
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.events.sync import SyncLifecycleEvent
from airweave.core.logging import logger
from airweave.core.protocols.event_bus import EventBus
from airweave.core.shared_models import SyncJobStatus
from airweave.db.session import get_db_context
from airweave.domains.sync_pipeline.pipeline.entity_tracker import SyncStats
from airweave.domains.syncs.protocols import SyncJobStateMachineProtocol
from airweave.schemas.sync_job import SyncJobUpdate

if TYPE_CHECKING:
    from airweave.domains.syncs.protocols import SyncJobRepositoryProtocol

# ---------------------------------------------------------------------------
# Transition graph
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[SyncJobStatus, set[SyncJobStatus]] = {
    SyncJobStatus.PENDING: {
        SyncJobStatus.RUNNING,
        SyncJobStatus.CANCELLED,
        SyncJobStatus.FAILED,
    },
    SyncJobStatus.RUNNING: {
        SyncJobStatus.COMPLETED,
        SyncJobStatus.FAILED,
        SyncJobStatus.CANCELLING,
    },
    SyncJobStatus.CANCELLING: {
        SyncJobStatus.CANCELLED,
    },
    SyncJobStatus.COMPLETED: set(),
    SyncJobStatus.FAILED: set(),
    SyncJobStatus.CANCELLED: set(),
}

_LIFECYCLE_EVENT_FACTORY = {
    SyncJobStatus.PENDING: SyncLifecycleEvent.pending,
    SyncJobStatus.RUNNING: SyncLifecycleEvent.running,
    SyncJobStatus.COMPLETED: SyncLifecycleEvent.completed,
    SyncJobStatus.FAILED: SyncLifecycleEvent.failed,
    SyncJobStatus.CANCELLED: SyncLifecycleEvent.cancelled,
}

# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LifecycleData:
    """Identifiers needed to publish a SyncLifecycleEvent."""

    organization_id: UUID
    sync_id: UUID
    sync_job_id: UUID
    collection_id: UUID
    source_connection_id: UUID
    source_type: str = ""
    collection_name: str = ""
    collection_readable_id: str = ""


@dataclass(frozen=True)
class TransitionResult:
    """Outcome of a transition attempt."""

    applied: bool
    previous: SyncJobStatus
    current: SyncJobStatus


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class InvalidTransitionError(Exception):
    """Raised when a status transition violates the state machine graph."""

    def __init__(
        self,
        current: SyncJobStatus,
        target: SyncJobStatus,
        sync_job_id: UUID | str | None = None,
    ) -> None:
        """Initialize with current/target status and optional job ID."""
        self.current = current
        self.target = target
        self.sync_job_id = sync_job_id
        job = f" for job {sync_job_id}" if sync_job_id else ""
        super().__init__(f"Invalid transition {current.value} → {target.value}{job}")


# ---------------------------------------------------------------------------
# Pure validation (usable without DB/event bus)
# ---------------------------------------------------------------------------


def validate_transition(
    current: SyncJobStatus,
    target: SyncJobStatus,
    sync_job_id: UUID | str | None = None,
) -> None:
    """Raise InvalidTransitionError if the transition is not allowed.

    Same-status re-writes are allowed (idempotent).
    """
    if target == current:
        return
    allowed = _VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidTransitionError(current, target, sync_job_id)


# ---------------------------------------------------------------------------
# State machine service
# ---------------------------------------------------------------------------


@dataclass
class SyncJobStateMachine(SyncJobStateMachineProtocol):
    """Validates transitions, writes to DB, and publishes lifecycle events.

    Idempotent: if the job is already in the target state, returns
    ``TransitionResult(applied=False)`` without touching DB or event bus.

    Dependencies:
        sync_job_repo: Read current status + persist updates
        event_bus: Publish SyncLifecycleEvent after successful DB write
    """

    sync_job_repo: SyncJobRepositoryProtocol
    event_bus: EventBus

    async def transition(
        self,
        sync_job_id: UUID,
        target: SyncJobStatus,
        ctx: BaseContext,
        *,
        lifecycle_data: Optional[LifecycleData] = None,
        error: Optional[str] = None,
        stats: Optional[SyncStats] = None,
    ) -> TransitionResult:
        """Execute a validated, idempotent status transition.

        Args:
            sync_job_id: The job to transition.
            target: Desired status.
            ctx: Context for DB scoping and logging.
            lifecycle_data: If provided, publish a SyncLifecycleEvent.
            error: Error message (valid for FAILED and CANCELLED).
            stats: Sync statistics (valid for any terminal state).

        Returns:
            TransitionResult indicating whether the write was applied.

        Raises:
            InvalidTransitionError: If the transition is illegal.
        """
        async with get_db_context() as db:
            db_job = await self.sync_job_repo.get(db=db, id=sync_job_id, ctx=ctx)
            if not db_job:
                logger.error(f"Sync job {sync_job_id} not found")
                return TransitionResult(
                    applied=False,
                    previous=SyncJobStatus.PENDING,
                    current=SyncJobStatus.PENDING,
                )

            current = SyncJobStatus(db_job.status)

            if current == target:
                logger.debug(f"Sync job {sync_job_id} already in {target.value} (idempotent skip)")
                return TransitionResult(applied=False, previous=current, current=current)

            validate_transition(current, target, sync_job_id)

            update = self._build_update(target, error=error, stats=stats)
            await self.sync_job_repo.update(db=db, db_obj=db_job, obj_in=update, ctx=ctx)
            await db.commit()

        logger.info(f"Sync job {sync_job_id}: {current.value} → {target.value}")

        if lifecycle_data is not None:
            await self._publish_lifecycle_event(target, lifecycle_data, error=error)

        return TransitionResult(applied=True, previous=current, current=target)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_update(
        target: SyncJobStatus,
        *,
        error: Optional[str] = None,
        stats: Optional[SyncStats] = None,
    ) -> SyncJobUpdate:
        """Derive the SyncJobUpdate from target status."""
        data: dict = {"status": target}
        now = utc_now_naive()

        if target == SyncJobStatus.RUNNING:
            data["started_at"] = now
        elif target == SyncJobStatus.COMPLETED:
            data["completed_at"] = now
        elif target == SyncJobStatus.FAILED:
            data["failed_at"] = now
        elif target == SyncJobStatus.CANCELLED:
            data["completed_at"] = now

        if error is not None and target in (SyncJobStatus.FAILED, SyncJobStatus.CANCELLED):
            data["error"] = error

        if stats is not None:
            data["entities_inserted"] = stats.inserted
            data["entities_updated"] = stats.updated
            data["entities_deleted"] = stats.deleted
            data["entities_kept"] = stats.kept
            data["entities_skipped"] = stats.skipped
            data["entities_encountered"] = stats.entities_encountered

        return SyncJobUpdate(**data)

    async def _publish_lifecycle_event(
        self,
        target: SyncJobStatus,
        ld: LifecycleData,
        *,
        error: Optional[str] = None,
    ) -> None:
        """Publish the appropriate SyncLifecycleEvent for the target status."""
        factory = _LIFECYCLE_EVENT_FACTORY.get(target)
        if factory is None:
            return

        kwargs: dict = {
            "organization_id": ld.organization_id,
            "sync_id": ld.sync_id,
            "sync_job_id": ld.sync_job_id,
            "collection_id": ld.collection_id,
            "source_connection_id": ld.source_connection_id,
            "source_type": ld.source_type,
            "collection_name": ld.collection_name,
            "collection_readable_id": ld.collection_readable_id,
        }

        if target == SyncJobStatus.FAILED and error is not None:
            kwargs["error"] = error

        try:
            await self.event_bus.publish(factory(**kwargs))
        except Exception as e:
            logger.warning(f"Failed to publish lifecycle event for {target.value}: {e}")
