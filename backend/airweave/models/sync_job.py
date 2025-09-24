"""Sync job model."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, TypeDecorator
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.core.shared_models import SyncJobStatus
from airweave.models._base import OrganizationBase, UserMixin


class MappedSyncJobStatus(TypeDecorator):
    """Custom SQLAlchemy type that maps between Python and Database enum values.

    Python: pending, running, completed, failed, cancelled
    Database: PENDING, IN_PROGRESS, COMPLETED, FAILED, CANCELLED
    """

    # Use the actual PostgreSQL enum as the implementation
    impl = ENUM(
        "PENDING",
        "IN_PROGRESS",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
        name="syncjobstatus",
        create_type=False,
    )
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Convert Python enum to database string."""
        if value is None:
            return None
        if isinstance(value, SyncJobStatus):
            # Map RUNNING to IN_PROGRESS for database
            if value == SyncJobStatus.RUNNING:
                return "IN_PROGRESS"
            return value.value.upper()
        # Handle string values by normalizing them
        if isinstance(value, str):
            # Map "running" to IN_PROGRESS to avoid enum constraint errors
            if value.lower() == "running":
                return "IN_PROGRESS"
            return value.upper()
        return value

    def process_result_value(self, value, dialect):
        """Convert database string to Python enum."""
        if value is None:
            return None
        # Map IN_PROGRESS back to RUNNING for Python
        if value == "IN_PROGRESS":
            return SyncJobStatus.RUNNING
        # Convert other uppercase values to lowercase and create enum
        try:
            return SyncJobStatus(value.lower())
        except ValueError:
            # Fallback for unknown values
            return value


if TYPE_CHECKING:
    from airweave.models.entity import Entity
    from airweave.models.sync import Sync


class SyncJob(OrganizationBase, UserMixin):
    """Sync job model."""

    __tablename__ = "sync_job"

    sync_id: Mapped[UUID] = mapped_column(
        ForeignKey("sync.id", ondelete="CASCADE", name="fk_sync_job_sync_id"), nullable=False
    )
    status: Mapped[SyncJobStatus] = mapped_column(
        MappedSyncJobStatus(), default=SyncJobStatus.PENDING
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    entities_inserted: Mapped[int] = mapped_column(Integer, default=0)
    entities_updated: Mapped[int] = mapped_column(Integer, default=0)
    entities_deleted: Mapped[int] = mapped_column(Integer, default=0)
    entities_kept: Mapped[int] = mapped_column(Integer, default=0)
    entities_skipped: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    entities_encountered: Mapped[Optional[dict]] = mapped_column(JSON, default={})
    scheduled: Mapped[bool] = mapped_column(Boolean, default=False)

    sync: Mapped["Sync"] = relationship(
        "Sync",
        back_populates="jobs",
        lazy="noload",
    )

    entities: Mapped[list["Entity"]] = relationship(
        "Entity",
        back_populates="sync_job",
        lazy="noload",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
