"""add embedding config columns to collection

Revision ID: s5t6u7v8w9x0
Revises: r4s5t6u7v8w9
Create Date: 2026-02-23 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "s5t6u7v8w9x0"
down_revision = "r4s5t6u7v8w9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("collection", sa.Column("vector_size", sa.Integer(), nullable=True))
    op.add_column("collection", sa.Column("embedding_model_name", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("collection", "embedding_model_name")
    op.drop_column("collection", "vector_size")
