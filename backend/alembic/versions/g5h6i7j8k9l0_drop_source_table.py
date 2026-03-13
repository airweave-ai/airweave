"""Drop source table.

Revision ID: g5h6i7j8k9l0
Revises: f4g5h6i7j8k9
Create Date: 2026-03-10

"""

from alembic import op

revision = "g5h6i7j8k9l0"
down_revision = "f4g5h6i7j8k9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("source")


def downgrade() -> None:
    raise NotImplementedError("Cannot recreate source table — data now lives in SourceRegistry.")
