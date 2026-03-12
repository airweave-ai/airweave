"""Drop destination table.

Revision ID: f4g5h6i7j8k9
Revises: e3f4g5h6i7j8
Create Date: 2026-03-10 12:00:00.000000
"""

from alembic import op

revision = "f4g5h6i7j8k9"
down_revision = "e3f4g5h6i7j8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("destination")


def downgrade() -> None:
    raise RuntimeError("Irreversible migration — destination table cannot be recreated.")
