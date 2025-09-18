"""merge_search_queries_and_entity_count

Revision ID: 9f7826727a55
Revises: add_entity_count, b2c3d4e5f6a7
Create Date: 2025-09-17 09:13:12.995309

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9f7826727a55'
down_revision = ('add_entity_count', 'b2c3d4e5f6a7')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
