"""Add sigv4 to authtype enum

Revision ID: 535b39a9b0b5
Revises: e2819d7d0588
Create Date: 2025-04-22 02:20:18.737543

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '535b39a9b0b5'
down_revision = 'e2819d7d0588'
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
