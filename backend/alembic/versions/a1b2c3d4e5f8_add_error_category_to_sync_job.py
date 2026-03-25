"""Add error_category column to sync_job table.

Revision ID: a1b2c3d4e5f8
Revises: s5t6u7v8w9x0
Create Date: 2026-03-21
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f8"
down_revision = "s5t6u7v8w9x0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sync_job", sa.Column("error_category", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("sync_job", "error_category")
