"""Sync model."""

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from sqlalchemy import JSON, DateTime, String, event, text
from sqlalchemy import Connection as SAConnection
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.core.logging import logger
from airweave.core.shared_models import SyncJobStatus, SyncStatus
from airweave.domains.temporal import schedule_ids as temporal_schedule_ids
from airweave.domains.temporal.client import get_client as get_temporal_client
from airweave.models._base import OrganizationBase, UserMixin

if TYPE_CHECKING:
    from airweave.models.entity import Entity
    from airweave.models.source_connection import SourceConnection
    from airweave.models.sync_connection import SyncConnection
    from airweave.models.sync_cursor import SyncCursor
    from airweave.models.sync_job import SyncJob


class Sync(OrganizationBase, UserMixin):
    """Sync model."""

    __tablename__ = "sync"

    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[SyncStatus] = mapped_column(default=SyncStatus.ACTIVE)
    cron_schedule: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    next_scheduled_run: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    temporal_schedule_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sync_type: Mapped[str] = mapped_column(String(50), default="full")
    pause_reason: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    sync_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    sync_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    jobs: Mapped[list["SyncJob"]] = relationship(
        "SyncJob",
        back_populates="sync",
        lazy="noload",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    entities: Mapped[list["Entity"]] = relationship(
        "Entity",
        back_populates="sync",
        lazy="noload",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    sync_connections: Mapped[list["SyncConnection"]] = relationship(
        "SyncConnection",
        back_populates="sync",
        lazy="noload",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    source_connection: Mapped[Optional["SourceConnection"]] = relationship(
        "SourceConnection",
        back_populates="sync",
        lazy="noload",
        passive_deletes=True,
    )

    # Add relationship to SyncCursor (one-to-one)
    sync_cursor: Mapped[Optional["SyncCursor"]] = relationship(
        "SyncCursor",
        back_populates="sync",
        lazy="noload",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,  # Ensures one-to-one relationship
    )


def cancel_running_sync_jobs(connection: SAConnection, sync_id: UUID) -> None:
    """Cancel any running or pending jobs for the given sync.

    Called from ORM event listeners and from source_connection cleanup.
    Best-effort: failures are logged but do not propagate.
    """

    async def _cancel_workflow(workflow_job_id: str) -> None:
        client = await get_temporal_client()
        workflow_id = f"sync-{workflow_job_id}"
        try:
            handle = client.get_workflow_handle(workflow_id)
            await handle.cancel()
            logger.info(f"Requested Temporal cancellation for workflow {workflow_id}")
        except Exception as e:
            logger.debug(f"Could not cancel Temporal workflow {workflow_id}: {e}")

    try:
        result = connection.execute(
            text(
                """
                SELECT id, status FROM sync_job
                WHERE sync_id = :sync_id
                  AND status IN (:pending, :running)
                ORDER BY created_at DESC
                """
            ),
            {
                "sync_id": str(sync_id),
                "pending": SyncJobStatus.PENDING.value,
                "running": SyncJobStatus.RUNNING.value,
            },
        )

        for job in result:
            job_id = job[0]
            logger.info(f"Cancelling job {job_id} for sync {sync_id} before deletion")

            connection.execute(
                text(
                    """
                    UPDATE sync_job
                    SET status = :status,
                        modified_at = CURRENT_TIMESTAMP
                    WHERE id = :job_id
                    """
                ),
                {"status": SyncJobStatus.CANCELLING.value, "job_id": str(job_id)},
            )

            try:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(_cancel_workflow(job_id))
                except RuntimeError:
                    asyncio.run(_cancel_workflow(job_id))
            except Exception as e:
                logger.debug(f"Could not request Temporal cancellation for job {job_id}: {e}")
    except Exception as e:
        logger.warning(f"Error cancelling jobs for sync {sync_id}: {e}")


def cleanup_temporal_schedules(sync_id: UUID) -> None:
    """Delete Temporal schedules for the given sync.

    Called from ORM event listeners and from source_connection cleanup.
    Best-effort: failures are logged but do not propagate.
    """
    try:
        sids = temporal_schedule_ids.all_schedule_ids(sync_id)

        async def _cleanup() -> None:
            # [code blue] todo: replace ORM listener with EventBus subscriber
            from airweave.core import container as container_mod

            if container_mod.container is None:
                return
            schedule_svc = container_mod.container.temporal_schedule_service
            for sid in sids:
                await schedule_svc.delete_schedule_handle(sid)

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_cleanup())
        except RuntimeError:
            asyncio.run(_cleanup())
    except Exception as e:
        logger.info(f"Could not schedule Temporal cleanup for sync {sync_id}: {e}")


# Cancel any running jobs when a Sync is deleted (covers cascades)
@event.listens_for(Sync, "before_delete")
def cancel_running_jobs_before_sync_delete(mapper: Any, connection: Any, target: Any) -> None:
    """Cancel any running or pending jobs when a Sync is deleted."""
    cancel_running_sync_jobs(connection, target.id)


# Ensure Temporal schedules are deleted when a Sync row is deleted (covers cascades)
@event.listens_for(Sync, "after_delete")
def delete_temporal_schedules_after_sync_delete(mapper: Any, connection: Any, target: Any) -> None:
    """Delete Temporal schedules when a Sync row is deleted."""
    cleanup_temporal_schedules(target.id)
