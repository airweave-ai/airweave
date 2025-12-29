"""Sync connection model."""

from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import Base

if TYPE_CHECKING:
    from airweave.models.connection import Connection
    from airweave.models.sync import Sync


class DestinationRole(str, Enum):
    """Role of a destination in a sync for multiplexing support.

    Used to enable blue-green deployments and migrations between vector DB configs.
    """

    ACTIVE = "active"  # Receives writes + serves queries
    SHADOW = "shadow"  # Receives writes only (for migration testing)
    DEPRECATED = "deprecated"  # No longer in use (kept for rollback)


class SyncConnection(Base):
    """Sync connection model.

    Links syncs to their source and destination connections.
    For destinations, the `role` field enables multiplexing for migrations.
    """

    __tablename__ = "sync_connection"

    sync_id: Mapped[UUID] = mapped_column(ForeignKey("sync.id", ondelete="CASCADE"), nullable=False)
    connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("connection.id", ondelete="CASCADE"), nullable=False
    )
    # Role for destination connections (active/shadow/deprecated)
    # Used for blue-green deployments and migrations
    role: Mapped[str] = mapped_column(
        String(20), default=DestinationRole.ACTIVE.value, nullable=False
    )

    # Add relationship back to Sync
    sync: Mapped["Sync"] = relationship("Sync", back_populates="sync_connections")
    connection: Mapped["Connection"] = relationship(
        "Connection",
        back_populates="sync_connections",
        lazy="noload",
    )
