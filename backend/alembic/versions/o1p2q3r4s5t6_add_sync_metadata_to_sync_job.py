"""Add sync_metadata column to sync_job.

Adds sync_metadata JSONB column for storing metadata like tags.
This is separate from sync_config which is for execution configuration.

Revision ID: o1p2q3r4s5t6
Revises: n7o8p9q0r1s2
Create Date: 2026-01-22 10:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "o1p2q3r4s5t6"
down_revision = "n7o8p9q0r1s2"
branch_labels = None
depends_on = None


def upgrade():
    """Add sync_metadata column to sync_job."""
    op.add_column(
        "sync_job",
        sa.Column("sync_metadata", postgresql.JSONB(), nullable=True),
    )


def downgrade():
    """Remove sync_metadata column from sync_job."""
    op.drop_column("sync_job", "sync_metadata")

