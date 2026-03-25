"""add description to api_key

Revision ID: 6d0b927a491b
Revises: 779ea3740ec4
Create Date: 2026-03-24 20:21:52.403429

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6d0b927a491b'
down_revision = '779ea3740ec4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "api_key",
        sa.Column("description", sa.String(255), nullable=True),
    )


def downgrade():
    op.drop_column("api_key", "description")
