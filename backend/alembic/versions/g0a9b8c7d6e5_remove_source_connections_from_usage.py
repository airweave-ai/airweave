"""Remove source_connections from usage table

Revision ID: g0a9b8c7d6e5
Revises: f9a8b7c6d5e4
Create Date: 2025-01-12 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g0a9b8c7d6e5'
down_revision = 'f9a8b7c6d5e4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove source_connections column from usage table.
    
    Source connections are now counted directly from the source_connection table
    (like team_members from user_organization), not tracked in usage.
    """
    op.drop_column('usage', 'source_connections')


def downgrade() -> None:
    """Re-add source_connections column (will be empty/zero)."""
    op.add_column(
        'usage',
        sa.Column(
            'source_connections',
            sa.Integer(),
            nullable=False,
            server_default='0'
        )
    )

