"""add_vector_size_to_collection

Revision ID: add_vector_size_to_collection
Revises: bf10682f1193
Create Date: 2025-09-17 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "add_vector_size_to_collection"
down_revision = "bf10682f1193"
branch_labels = None
depends_on = None


def upgrade():
    # Add vector_size column to collection table
    op.add_column("collection", sa.Column("vector_size", sa.Integer(), nullable=True))


def downgrade():
    # Remove vector_size column from collection table
    op.drop_column("collection", "vector_size")