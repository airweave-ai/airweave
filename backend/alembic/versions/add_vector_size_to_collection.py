"""add_vector_size_to_collection

Revision ID: 7f8a9b2c3d4e
Revises: 0765a96ad189
Create Date: 2025-09-17 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7f8a9b2c3d4e"
down_revision = "0765a96ad189"
branch_labels = None
depends_on = None


def upgrade():
    # Add vector_size column to collection table
    op.add_column("collection", sa.Column("vector_size", sa.Integer(), nullable=True))


def downgrade():
    # Remove vector_size column from collection table
    op.drop_column("collection", "vector_size")