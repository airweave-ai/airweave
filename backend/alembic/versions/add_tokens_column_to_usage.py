"""Add tokens column to usage table for agentic search tracking.

Revision ID: 7f3a9c2b1d4e
Revises: 8bdd5dcf7837, b2c3d4e5f6g7, c9d0e1f2a3b4, g5h6i7j8k9l0
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7f3a9c2b1d4e"
down_revision = ("8bdd5dcf7837", "b2c3d4e5f6g7", "c9d0e1f2a3b4", "g5h6i7j8k9l0")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "usage",
        sa.Column("tokens", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("usage", "tokens")
