"""Add data_tree_node and node_selection tables.

Revision ID: b2c3d4e5f6g7
Revises: b788750e60fe
Create Date: 2026-03-03 00:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6g7"
down_revision = "b788750e60fe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create data_tree_node and node_selection tables with indexes."""
    # 1. data_tree_node
    op.create_table(
        "data_tree_node",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("modified_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "organization_id",
            UUID,
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_connection_id",
            UUID,
            sa.ForeignKey("source_connection.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            UUID,
            sa.ForeignKey("data_tree_node.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("node_type", sa.String(20), nullable=False),
        sa.Column("source_node_id", sa.String(512), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("item_count", sa.Integer(), nullable=True),
        sa.Column("node_metadata", JSONB, nullable=True),
        sa.Column("access_viewers", JSONB, nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    # Indexes for data_tree_node
    op.create_index("idx_data_tree_node_org", "data_tree_node", ["organization_id"])
    op.create_index("idx_data_tree_node_source_conn", "data_tree_node", ["source_connection_id"])
    op.create_index("idx_data_tree_node_parent", "data_tree_node", ["parent_id"])
    op.create_index(
        "uq_data_tree_node_source_node",
        "data_tree_node",
        ["source_connection_id", "source_node_id"],
        unique=True,
    )

    # GIN index on access_viewers for ?| (overlap) queries.
    # Must use default jsonb_ops (not jsonb_path_ops) because ?| is not
    # supported by the jsonb_path_ops operator class.
    op.execute(
        "CREATE INDEX idx_data_tree_node_access_viewers "
        "ON data_tree_node USING GIN (access_viewers)"
    )

    # 2. node_selection
    op.create_table(
        "node_selection",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("modified_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "organization_id",
            UUID,
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_connection_id",
            UUID,
            sa.ForeignKey("source_connection.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_node_id", sa.String(512), nullable=False),
        sa.Column("node_type", sa.String(20), nullable=False),
        sa.Column("node_title", sa.String(512), nullable=True),
        sa.Column("node_metadata", JSONB, nullable=True),
    )

    # Indexes for node_selection
    op.create_index("idx_node_selection_org", "node_selection", ["organization_id"])
    op.create_index("idx_node_selection_source_conn", "node_selection", ["source_connection_id"])
    op.create_index(
        "uq_node_selection_source_node",
        "node_selection",
        ["source_connection_id", "source_node_id"],
        unique=True,
    )


def downgrade() -> None:
    """Drop node_selection and data_tree_node tables."""
    op.drop_table("node_selection")
    op.drop_index("idx_data_tree_node_access_viewers", table_name="data_tree_node")
    op.drop_table("data_tree_node")
