"""Sync model."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, DateTime, String, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.core.logging import logger
from airweave.core.shared_models import SyncStatus
from airweave.models._base import OrganizationBase, UserMixin

if TYPE_CHECKING:
    from airweave.models.dag import SyncDag
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
    minute_level_cron_schedule: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sync_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

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

    # Add relationship to SyncDag
    sync_dag: Mapped[Optional["SyncDag"]] = relationship(
        "SyncDag",
        back_populates="sync",
        lazy="noload",
        cascade="all, delete-orphan",
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


# Ensure Temporal schedules are deleted when a Sync row is deleted (covers cascades)
@event.listens_for(Sync, "after_delete")
def delete_temporal_schedules_after_sync_delete(mapper, connection, target):
    """Delete Temporal schedules when a Sync row is deleted."""
    try:
        import asyncio

        schedule_ids = [
            f"minute-sync-{target.id}",
            f"daily-cleanup-{target.id}",
        ]

        async def _cleanup():
            # Import here to avoid circular import during module initialization
            from airweave.platform.temporal.schedule_service import (
                temporal_schedule_service,
            )

            for sid in schedule_ids:
                await temporal_schedule_service.delete_schedule_handle(sid)

        asyncio.get_event_loop().create_task(_cleanup())
    except Exception as e:
        logger.info(
            f"Could not schedule Temporal cleanup for sync {getattr(target, 'id', None)}: {e}"
        )
