"""Add failure tracking fields to source_connection

Revision ID: h1b0c9d8e7f6
Revises: g0a9b8c7d6e5
Create Date: 2025-01-13 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "h1b0c9d8e7f6"
down_revision = "g0a9b8c7d6e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add failure tracking fields to source_connection table."""
    # Add consecutive_failures counter
    op.add_column(
        "source_connection",
        sa.Column(
            "consecutive_failures", sa.Integer(), nullable=False, server_default="0"
        ),
    )

    # Add last_failure_at timestamp
    op.add_column(
        "source_connection",
        sa.Column("last_failure_at", sa.DateTime(), nullable=True),
    )

    # Add last_failure_reason (user-friendly message)
    op.add_column(
        "source_connection",
        sa.Column("last_failure_reason", sa.Text(), nullable=True),
    )

    # Add last_failure_category (AUTH, VALIDATION, CONFIG, etc.)
    op.add_column(
        "source_connection",
        sa.Column("last_failure_category", sa.String(), nullable=True),
    )

    # Add health_status (HEALTHY, DEGRADED, BLOCKED, REQUIRES_AUTH)
    op.add_column(
        "source_connection",
        sa.Column(
            "health_status",
            sa.String(),
            nullable=False,
            server_default="HEALTHY",
        ),
    )


def downgrade() -> None:
    """Remove failure tracking fields from source_connection table."""
    op.drop_column("source_connection", "health_status")
    op.drop_column("source_connection", "last_failure_category")
    op.drop_column("source_connection", "last_failure_reason")
    op.drop_column("source_connection", "last_failure_at")
    op.drop_column("source_connection", "consecutive_failures")

