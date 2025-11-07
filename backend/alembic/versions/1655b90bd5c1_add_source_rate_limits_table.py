"""add_source_rate_limits_table

Revision ID: 1655b90bd5c1
Revises: d702ba6de953
Create Date: 2025-11-03 17:09:37.384481

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1655b90bd5c1'
down_revision = 'd702ba6de953'
branch_labels = None
depends_on = None


def upgrade():
    # Add rate limit field to source table
    op.add_column('source', sa.Column('rate_limit_level', sa.String(), nullable=True))
    
    # Create source_rate_limits table (ONE row per org+source)
    op.create_table(
        'source_rate_limits',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('source_short_name', sa.String(), nullable=False),
        sa.Column('limit', sa.Integer(), nullable=False),
        sa.Column('window_seconds', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'source_short_name', name='uq_org_source_rate_limit')
    )
    
    # Create index for fast lookups
    op.create_index(
        'ix_source_rate_limits_lookup',
        'source_rate_limits',
        ['organization_id', 'source_short_name']
    )


def downgrade():
    # Drop index first
    op.drop_index('ix_source_rate_limits_lookup', table_name='source_rate_limits')
    
    # Drop table
    op.drop_table('source_rate_limits')
    
    # Drop source table column
    op.drop_column('source', 'rate_limit_level')
