"""Add supports_access_control column to source table.

Revision ID: j3k4l5m6n7o8
Revises: i2j3k4l5m6n7
Create Date: 2026-01-05 13:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "j3k4l5m6n7o8"
down_revision = "i2j3k4l5m6n7"
branch_labels = None
depends_on = None


def upgrade():
    """Add supports_access_control column to source table.

    This column indicates whether the source provides entity-level access
    control metadata. When True, the source:
    1. Sets entity.access on all yielded entities
    2. Implements generate_access_control_memberships() method
    """
    from sqlalchemy import inspect

    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("source")]

    if "supports_access_control" not in columns:
        op.add_column(
            "source",
            sa.Column(
                "supports_access_control",
                sa.Boolean(),
                nullable=False,
                server_default="false",
            ),
        )


def downgrade():
    """Remove supports_access_control column from source table."""
    op.drop_column("source", "supports_access_control")
