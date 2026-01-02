"""Sync connection model."""

from enum import Enum
from typing import TYPE_CHECKING, Optional
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

    Slicer table that links syncs to their source and destination connections.

    - For SOURCE connections: role is NULL (sources don't participate in multiplexing)
    - For DESTINATION connections: role is 'active', 'shadow', or 'deprecated' (used for blue-green deployments and migrations)
    """

    __tablename__ = "sync_connection"

    sync_id: Mapped[UUID] = mapped_column(ForeignKey("sync.id", ondelete="CASCADE"), nullable=False)
    connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("connection.id", ondelete="CASCADE"), nullable=False
    )
    # Role for destination connections only (NULL for sources)
    # Used for blue-green deployments and migrations
    role: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default=None)

    # Add relationship back to Sync
    sync: Mapped["Sync"] = relationship("Sync", back_populates="sync_connections")
    connection: Mapped["Connection"] = relationship(
        "Connection",
        back_populates="sync_connections",
        lazy="noload",
    )
