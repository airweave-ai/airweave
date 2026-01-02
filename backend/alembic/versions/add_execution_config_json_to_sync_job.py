"""Add execution_config_json column to sync_job for config-driven sync execution.

Revision ID: n7o8p9q0r1s2
Revises: h1i2j3k4l5m6
Create Date: 2025-01-02 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "n7o8p9q0r1s2"
down_revision = "h1i2j3k4l5m6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add execution_config_json column to sync_job table.

    Enables config-driven sync execution without bloating Temporal contract.
    Worker refetches SyncJob from DB to get execution config.
    
    Config controls:
    - Destination filtering (target/exclude)
    - Handler toggles (vector/ARF/postgres)
    - Behavior flags (skip hash comparison/updates)
    """
    op.add_column(
        "sync_job",
        sa.Column("execution_config_json", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    """Remove execution_config_json column from sync_job table."""
    op.drop_column("sync_job", "execution_config_json")

