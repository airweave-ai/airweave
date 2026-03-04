"""Data tree node model for browse tree metadata."""

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import OrganizationBase

if TYPE_CHECKING:
    from airweave.models.source_connection import SourceConnection


class DataTreeNode(OrganizationBase):
    """Metadata tree node produced by a metadata-only sync.

    Stores the hierarchy of a source's content (sites, lists, folders, files)
    along with ACL information for access-filtered browsing.

    The tree is org-wide but scoped to a source connection (admin's SC)
    to identify which source instance produced it.
    """

    __tablename__ = "data_tree_node"

    # Which source connection (admin's SC) produced this tree
    source_connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_connection.id", ondelete="CASCADE"), nullable=False
    )

    # Self-referential parent for tree structure
    parent_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("data_tree_node.id", ondelete="CASCADE"), nullable=True
    )

    # Node identity
    node_type: Mapped[str] = mapped_column(String(20), nullable=False)  # site/list/folder/file/item
    source_node_id: Mapped[str] = mapped_column(
        String(512), nullable=False
    )  # SP GUID or composite ID
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Aggregate metadata
    item_count: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Flexible metadata (url, file_name, base_template, etc.)
    node_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Access control
    access_viewers: Mapped[Optional[list]] = mapped_column(
        JSONB, nullable=True
    )  # ["user:john", "group:sp:site_members"]
    is_public: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Relationships
    source_connection: Mapped["SourceConnection"] = relationship("SourceConnection", lazy="noload")
    parent: Mapped[Optional["DataTreeNode"]] = relationship(
        "DataTreeNode", remote_side="DataTreeNode.id", lazy="noload"
    )

    __table_args__ = (
        # Unique per source connection + source node
        Index(
            "uq_data_tree_node_source_node",
            "source_connection_id",
            "source_node_id",
            unique=True,
        ),
        # Tree traversal by parent
        Index("idx_data_tree_node_parent", "parent_id"),
        # Lookup by source connection for cleanup
        Index("idx_data_tree_node_source_conn", "source_connection_id"),
    )
