"""Sync model."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.core.shared_models import SyncStatus
from airweave.models._base import OrganizationBase, UserMixin

if TYPE_CHECKING:
    from airweave.models.entity import Entity
    from airweave.models.sync_connection import SyncConnection
    from airweave.models.sync_job import SyncJob
    from airweave.models.white_label import WhiteLabel


class Sync(OrganizationBase, UserMixin):
    """Sync model."""

    __tablename__ = "sync"

    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[SyncStatus] = mapped_column(default=SyncStatus.ACTIVE)
    cron_schedule: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    next_scheduled_run: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    white_label_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("white_label.id"), nullable=True
    )
    white_label_user_identifier: Mapped[str] = mapped_column(String(256), nullable=True)
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

    white_label: Mapped[Optional["WhiteLabel"]] = relationship(
        "WhiteLabel",
        back_populates="syncs",
        lazy="noload",
    )

    __table_args__ = (
        UniqueConstraint(
            "white_label_id",
            "white_label_user_identifier",
            name="uq_white_label_user",
        ),
    )
