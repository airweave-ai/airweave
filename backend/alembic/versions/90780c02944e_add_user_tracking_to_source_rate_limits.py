"""add_user_tracking_to_source_rate_limits

Revision ID: 90780c02944e
Revises: 1655b90bd5c1
Create Date: 2025-11-04 16:16:10.544564

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '90780c02944e'
down_revision = '1655b90bd5c1'
branch_labels = None
depends_on = None


def upgrade():
    # Add user tracking fields to source_rate_limits table
    op.add_column('source_rate_limits', sa.Column('created_by_email', sa.String(), nullable=True))
    op.add_column('source_rate_limits', sa.Column('modified_by_email', sa.String(), nullable=True))


def downgrade():
    # Remove user tracking fields
    op.drop_column('source_rate_limits', 'modified_by_email')
    op.drop_column('source_rate_limits', 'created_by_email')
