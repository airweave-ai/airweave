"""Add execution_config_json to sync_job.

Revision ID: h1i2j3k4l5m6
Revises: g0a9b8c7d6e5
Create Date: 2026-01-03 17:27:16.572060

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "h1i2j3k4l5m6"
down_revision = "g0a9b8c7d6e5"
branch_labels = None
depends_on = None


def upgrade():
    """Add execution_config_json column to sync_job table."""
    op.add_column(
        "sync_job",
        sa.Column("execution_config_json", postgresql.JSONB(), nullable=True),
    )


def downgrade():
    """Remove execution_config_json column from sync_job table."""
    op.drop_column("sync_job", "execution_config_json")
