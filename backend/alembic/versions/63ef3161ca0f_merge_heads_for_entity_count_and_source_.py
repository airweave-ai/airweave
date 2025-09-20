"""merge heads for entity count and source connection link

Revision ID: 63ef3161ca0f
Revises: 996fff04cc59, add_entity_count
Create Date: 2025-09-08 15:17:00.369196

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '63ef3161ca0f'
down_revision = ('996fff04cc59', 'add_entity_count')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
