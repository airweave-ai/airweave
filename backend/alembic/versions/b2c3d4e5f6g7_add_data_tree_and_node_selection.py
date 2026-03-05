"""Add node_selection table.

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
    """Create node_selection table with indexes."""
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
    """Drop node_selection table."""
    op.drop_table("node_selection")
