"""add_execution_config_json_to_sync_job

Revision ID: 9ff3dddc32fe
Revises: h1i2j3k4l5m6
Create Date: 2026-01-02 17:27:16.572060

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '9ff3dddc32fe'
down_revision = 'h1i2j3k4l5m6'
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
