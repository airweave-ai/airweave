"""merge heads for pricing changes

Revision ID: 518e7d92c2ef
Revises: 51f41d4cb9db, add_yearly_prepay_001
Create Date: 2025-09-22 20:22:15.208450

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '518e7d92c2ef'
down_revision = ('51f41d4cb9db', 'add_yearly_prepay_001')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
