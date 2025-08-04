"""add_temporal_schedule_fields_to_sync

Revision ID: 478587386b42
Revises: 6ae6a2cc0290
Create Date: 2025-08-04 17:53:51.923726

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '478587386b42'
down_revision = '6ae6a2cc0290'
branch_labels = None
depends_on = None


def upgrade():
    """Add Temporal schedule fields to sync table."""

    # Add temporal_schedule_id column to store the Temporal schedule ID
    op.add_column(
        "sync",
        sa.Column("temporal_schedule_id", sa.String(255), nullable=True)
    )

    # Add sync_type column to distinguish between full and incremental syncs
    op.add_column(
        "sync",
        sa.Column("sync_type", sa.String(50), nullable=False, server_default="full")
    )

    # Add minute_level_cron_schedule column for minute-level scheduling
    op.add_column(
        "sync",
        sa.Column("minute_level_cron_schedule", sa.String(100), nullable=True)
    )

    # Add index on temporal_schedule_id for efficient lookups
    op.create_index(
        "ix_sync_temporal_schedule_id",
        "sync",
        ["temporal_schedule_id"]
    )

    # Add index on sync_type for filtering
    op.create_index(
        "ix_sync_sync_type",
        "sync",
        ["sync_type"]
    )


def downgrade():
    """Remove Temporal schedule fields from sync table."""

    # Drop indexes
    op.drop_index("ix_sync_sync_type", "sync")
    op.drop_index("ix_sync_temporal_schedule_id", "sync")

    # Drop columns
    op.drop_column("sync", "minute_level_cron_schedule")
    op.drop_column("sync", "sync_type")
    op.drop_column("sync", "temporal_schedule_id")
