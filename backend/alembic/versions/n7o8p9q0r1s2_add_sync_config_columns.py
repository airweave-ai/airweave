"""Add sync_config columns to collection, sync, and sync_job.

Renames execution_config_json -> sync_config on sync_job.
Adds sync_config JSONB column to collection and sync tables.

Revision ID: n7o8p9q0r1s2
Revises: m6n7o8p9q0r1
Create Date: 2026-01-10 14:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "n7o8p9q0r1s2"
down_revision = "m6n7o8p9q0r1"
branch_labels = None
depends_on = None


def upgrade():
    """Add sync_config columns."""
    # Rename execution_config_json -> sync_config on sync_job
    op.alter_column(
        "sync_job",
        "execution_config_json",
        new_column_name="sync_config",
    )

    # Add sync_config to collection
    op.add_column(
        "collection",
        sa.Column("sync_config", postgresql.JSONB(), nullable=True),
    )

    # Add sync_config to sync
    op.add_column(
        "sync",
        sa.Column("sync_config", postgresql.JSONB(), nullable=True),
    )


def downgrade():
    """Remove sync_config columns."""
    # Remove sync_config from sync
    op.drop_column("sync", "sync_config")

    # Remove sync_config from collection
    op.drop_column("collection", "sync_config")

    # Rename sync_config -> execution_config_json on sync_job
    op.alter_column(
        "sync_job",
        "sync_config",
        new_column_name="execution_config_json",
    )
