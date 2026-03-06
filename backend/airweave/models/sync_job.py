"""Sync job model."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.core.shared_models import SyncJobStatus
from airweave.models._base import OrganizationBase, UserMixin

if TYPE_CHECKING:
    from airweave.models.entity import Entity
    from airweave.models.sync import Sync


class SyncJob(OrganizationBase, UserMixin):
    """Sync job model."""

    __tablename__ = "sync_job"

    sync_id: Mapped[UUID] = mapped_column(
        ForeignKey("sync.id", ondelete="CASCADE", name="fk_sync_job_sync_id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), default=SyncJobStatus.PENDING.value)
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
    sync_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    sync_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

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

    __table_args__ = (
        Index("idx_sync_job_sync_id", "sync_id"),
        Index("idx_sync_job_status", "status"),
        Index("idx_sync_job_status_modified_at", "status", "modified_at"),
        Index("idx_sync_job_status_started_at", "status", "started_at"),
    )
