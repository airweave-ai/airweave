"""merge vector_size and entity_count heads

Revision ID: e3db4e645396
Revises: add_entity_count, 7f8a9b2c3d4e
Create Date: 2025-09-18 00:47:33.512127

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e3db4e645396'
down_revision = ('add_entity_count', '7f8a9b2c3d4e')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
