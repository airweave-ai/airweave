"""Node selection model for user-selected browse tree nodes."""

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import OrganizationBase

if TYPE_CHECKING:
    from airweave.models.source_connection import SourceConnection


class NodeSelection(OrganizationBase):
    """A selected node for targeted sync.

    When a user picks nodes from the browse tree, each selection becomes
    a NodeSelection row linked to the source connection. During sync,
    the source reads these to do targeted fetches instead of a full crawl.
    """

    __tablename__ = "node_selection"

    # Source connection that owns these selections
    source_connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_connection.id", ondelete="CASCADE"), nullable=False
    )

    # Encoded source node ID (e.g., "site:url", "list:url|guid")
    source_node_id: Mapped[str] = mapped_column(String(512), nullable=False)
    node_type: Mapped[str] = mapped_column(String(20), nullable=False)
    node_title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Metadata needed for targeted fetch (site_url, list_id, etc.)
    node_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    source_connection: Mapped["SourceConnection"] = relationship("SourceConnection", lazy="noload")

    __table_args__ = (
        # Unique per source connection + source node
        Index(
            "uq_node_selection_source_node",
            "source_connection_id",
            "source_node_id",
            unique=True,
        ),
        # Lookup by source connection for loading selections
        Index("idx_node_selection_source_conn", "source_connection_id"),
    )
