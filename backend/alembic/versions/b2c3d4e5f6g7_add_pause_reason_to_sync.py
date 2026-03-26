"""Add pause_reason column to sync table.

Revision ID: b2c3d4e5f6g7
Revises: 0000
Create Date: 2026-03-26
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6g7"
down_revision = "0000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sync", sa.Column("pause_reason", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("sync", "pause_reason")
