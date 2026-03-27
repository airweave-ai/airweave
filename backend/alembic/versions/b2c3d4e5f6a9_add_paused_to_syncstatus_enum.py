"""Add PAUSED value to syncstatus enum.

Revision ID: b2c3d4e5f6a9
Revises: a1b2c3d4e5f8
Create Date: 2026-03-26
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a9"
down_revision = "a1b2c3d4e5f8"
branch_labels = None
depends_on = None


def upgrade() -> None:  # noqa: D103
    op.execute("ALTER TYPE syncstatus ADD VALUE IF NOT EXISTS 'PAUSED'")


def downgrade() -> None:  # noqa: D103
    pass
