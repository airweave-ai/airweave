"""Add role column to sync_connection for destination multiplexing

Revision ID: h1b0c9d8e7f6
Revises: remove_syncs_collections
Create Date: 2025-12-31

This migration:
1. Adds nullable 'role' column for destination multiplexing
2. Sets role='active' for existing DESTINATION connections (sources stay NULL)
3. Adds unique partial index to enforce single active destination per sync

Architecture:
- sync_connection stores BOTH source and destination connections
- Sources have role=NULL (they don't participate in multiplexing)
- Destinations have role='active', 'shadow', or 'deprecated'

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'h1b0c9d8e7f6'
down_revision = 'remove_syncs_collections'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add role column for destination multiplexing."""
    # 1. Add role column (nullable - sources will have NULL)
    op.add_column(
        'sync_connection',
        sa.Column('role', sa.String(20), nullable=True)
    )

    # 2. Set role='active' for existing DESTINATION connections only
    # Source connections keep role=NULL
    op.execute("""
        UPDATE sync_connection sc
        SET role = 'active'
        WHERE EXISTS (
            SELECT 1 FROM connection c
            WHERE c.id = sc.connection_id
            AND c.integration_type = 'DESTINATION'
        )
    """)

    # 3. Add unique partial index: only one active destination per sync
    # This only applies to destinations (role IS NOT NULL)
    op.execute("""
        CREATE UNIQUE INDEX ix_sync_connection_single_active
        ON sync_connection (sync_id)
        WHERE role = 'active'
    """)


def downgrade() -> None:
    """Remove role column and index from sync_connection table."""
    op.execute("DROP INDEX IF EXISTS ix_sync_connection_single_active")
    op.drop_column('sync_connection', 'role')
