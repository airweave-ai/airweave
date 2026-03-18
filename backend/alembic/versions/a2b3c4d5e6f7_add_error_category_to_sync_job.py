"""add error_category to sync_job

Revision ID: a2b3c4d5e6f7
Revises: 8bdd5dcf7837
Create Date: 2026-03-16 10:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a2b3c4d5e6f7"
down_revision = "8bdd5dcf7837"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sync_job", sa.Column("error_category", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("sync_job", "error_category")
