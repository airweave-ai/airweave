"""Add role column to sync_connection for destination multiplexing.

Revision ID: h1i2j3k4l5m6
Revises: g0a9b8c7d6e5
Create Date: 2024-12-29 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "h1i2j3k4l5m6"
down_revision = "g0a9b8c7d6e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add role column to sync_connection table.

    Enables destination multiplexing for blue-green deployments:
    - active: receives writes + serves queries
    - shadow: receives writes only (for testing)
    - deprecated: no longer in use (kept for rollback)
    """
    op.add_column(
        "sync_connection",
        sa.Column("role", sa.String(20), nullable=False, server_default="active"),
    )
    # Remove server default after setting existing rows
    op.alter_column("sync_connection", "role", server_default=None)


def downgrade() -> None:
    """Remove role column from sync_connection table."""
    op.drop_column("sync_connection", "role")
