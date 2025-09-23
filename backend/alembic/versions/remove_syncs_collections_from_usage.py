"""Remove syncs and collections columns from usage table

Revision ID: remove_syncs_collections
Revises: 518e7d92c2ef
Create Date: 2025-09-23

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'remove_syncs_collections'
down_revision = '518e7d92c2ef'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove syncs and collections columns from usage table."""
    # Drop the columns that are no longer tracked
    op.drop_column('usage', 'syncs')
    op.drop_column('usage', 'collections')


def downgrade() -> None:
    """Re-add syncs and collections columns to usage table."""
    # Re-add the columns with their original definitions
    op.add_column('usage', sa.Column('syncs', sa.Integer(), server_default='0', nullable=False))
    op.add_column('usage', sa.Column('collections', sa.Integer(), server_default='0', nullable=False))
