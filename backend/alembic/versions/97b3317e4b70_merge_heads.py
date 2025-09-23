"""merge heads

Revision ID: 97b3317e4b70
Revises: remove_syncs_collections
Create Date: 2025-09-23 20:31:56.545741

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '97b3317e4b70'
down_revision = ('4ee815df1fed', 'remove_syncs_collections')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
