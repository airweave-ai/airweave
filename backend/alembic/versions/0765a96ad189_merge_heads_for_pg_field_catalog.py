"""merge heads for pg_field_catalog

Revision ID: 0765a96ad189
Revises: 25e5ed7e5b9f, 4f2c1a7a9b10
Create Date: 2025-08-27 14:31:23.909286

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0765a96ad189'
down_revision = ('25e5ed7e5b9f', '4f2c1a7a9b10')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
