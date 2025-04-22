"""Add sigv4 to authtype enum

Revision ID: 4d8d11ed519e
Revises: 535b39a9b0b5
Create Date: 2025-04-22 02:22:37.192549

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4d8d11ed519e'
down_revision = '535b39a9b0b5'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add new enum value: auth_type='sigv4
    @author: Ton Hoang Nguyen (Bill), GitHub: @hahabill
    """
    op.execute("ALTER TYPE authtype ADD VALUE IF NOT EXISTS 'sigv4';")


def downgrade():
    pass
