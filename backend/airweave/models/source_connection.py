"""Source connection model."""

from time import sleep
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import text, JSON, ForeignKey, String, Text, event
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from airweave.models._base import OrganizationBase, UserMixin

if TYPE_CHECKING:
    from airweave.models.collection import Collection
    from airweave.models.connection import Connection
    from airweave.models.sync import Sync
    from airweave.models.white_label import WhiteLabel


class SourceConnection(OrganizationBase, UserMixin):
    """Source connection model for connecting to external data sources.

    This is a user-facing model that encompasses the connection and sync information for a
    specific source. Not to be confused with the connection model, which is a system table
    that contains the connection information for all integrations.
    """

    __tablename__ = "source_connection"

    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    short_name: Mapped[str] = mapped_column(String, nullable=False)  # Source short name

    # Configuration fields for the source connection
    config_fields: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Related objects
    sync_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("sync.id", ondelete="CASCADE"), nullable=True
    )
    readable_collection_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("collection.readable_id", ondelete="CASCADE"), nullable=True
    )
    connection_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("connection.id", ondelete="CASCADE"), nullable=True
    )
    white_label_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("white_label.id", ondelete="SET NULL"), nullable=True
    )
    # Status is now ephemeral - removed from database model

    # Relationships
    sync: Mapped[Optional["Sync"]] = relationship(
        "Sync",
        back_populates="source_connection",
        lazy="noload",
    )
    collection: Mapped[Optional["Collection"]] = relationship(
        "Collection",
        foreign_keys=[readable_collection_id],
        lazy="noload",
    )
    connection: Mapped[Optional["Connection"]] = relationship(
        "Connection",
        back_populates="source_connection",
        lazy="noload",
        cascade="all, delete-orphan",
        single_parent=True,
    )
    white_label: Mapped[Optional["WhiteLabel"]] = relationship(
        "WhiteLabel",
        back_populates="source_connections",
        lazy="noload",
    )


# Event to delete parent Sync when SourceConnection is deleted
@event.listens_for(SourceConnection, "before_delete")
def delete_parent_sync_and_connection(mapper, connection, target):
    """When a SourceConnection is deleted, also delete its parent Sync and Connection."""
    # Delete parent Sync if it exists
    if target.sync_id:
        # Get the session
        session = Session.object_session(target)
        if session:
            # If we're in a session, use the session to delete the Sync
            from airweave.models.sync import Sync

            sync = session.get(Sync, target.sync_id)
            if sync:
                session.delete(sync)
        else:
            # If we're not in a session, use the connection directly
            connection.execute(text("DELETE FROM sync WHERE id = ':target.sync_id"), {target.sync_id: target.sync_id})")

    sleep(0.2)

    # Delete related Connection if it exists
    if target.connection_id:
        session = Session.object_session(target)
        if session:
            from airweave.models.connection import Connection

            related_connection = session.get(Connection, target.connection_id)
            if related_connection:
                session.delete(related_connection)
        else:
            connection.execute(text("DELETE FROM connection WHERE id = ':target.connection_id"), {target.connection_id: target.connection_id})")
