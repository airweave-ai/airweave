"""Add pause_reason column to sync table.

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f8
Create Date: 2026-03-26
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6g7"
down_revision = "a1b2c3d4e5f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sync", sa.Column("pause_reason", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("sync", "pause_reason")
