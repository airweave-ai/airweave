"""Sync cursor model for storing incremental sync state."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import OrganizationBase

if TYPE_CHECKING:
    from airweave.models.sync import Sync


class SyncCursor(OrganizationBase):
    """Sync cursor model for storing incremental sync state.

    This model stores cursor information that allows a sync to resume
    from where it left off, enabling incremental syncs instead of full syncs.
    """

    __tablename__ = "sync_cursor"

    # TODO: sync_id is typed as str but sync.id is UUID.
    # Needs a data migration to fix — do not change the type without one.
    sync_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("sync.id", ondelete="CASCADE"), nullable=True, unique=True
    )

    # Cursor data stored as JSON
    cursor_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Cursor field name (e.g., 'last_repository_pushed_at' for GitHub)
    cursor_field: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Timestamp for tracking cursor updates
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationship to Sync (one-to-one)
    sync: Mapped[Optional["Sync"]] = relationship(
        "Sync",
        back_populates="sync_cursor",
        lazy="noload",
        passive_deletes=True,
    )
