"""Add Vespa destination to existing syncs.

Revision ID: m6n7o8p9q0r1
Revises: h1i2j3k4l5m6
Create Date: 2026-01-08 23:30:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "m6n7o8p9q0r1"
down_revision = "h1i2j3k4l5m6"
branch_labels = None
depends_on = None

# Native destination connection UUIDs (must match core/constants/reserved_ids.py)
QDRANT_CONNECTION_ID = "11111111-1111-1111-1111-111111111111"
VESPA_CONNECTION_ID = "33333333-3333-3333-3333-333333333333"


def upgrade():
    """Add Vespa destination connection to all syncs that have Qdrant but not Vespa."""
    op.execute(f"""
        INSERT INTO sync_connection (id, sync_id, connection_id, created_at, modified_at)
        SELECT 
            gen_random_uuid(),
            sc.sync_id,
            '{VESPA_CONNECTION_ID}'::uuid,
            NOW(),
            NOW()
        FROM sync_connection sc
        WHERE sc.connection_id = '{QDRANT_CONNECTION_ID}'::uuid
          AND NOT EXISTS (
            SELECT 1 
            FROM sync_connection sc2 
            WHERE sc2.sync_id = sc.sync_id 
              AND sc2.connection_id = '{VESPA_CONNECTION_ID}'::uuid
          );
    """)


def downgrade():
    """Remove Vespa destination connections that were added by this migration.
    
    NOTE: This is conservative and only removes Vespa connections for syncs
    that also have Qdrant (to avoid removing manually added Vespa connections).
    """
    op.execute(f"""
        DELETE FROM sync_connection
        WHERE connection_id = '{VESPA_CONNECTION_ID}'::uuid
          AND sync_id IN (
            SELECT sync_id 
            FROM sync_connection 
            WHERE connection_id = '{QDRANT_CONNECTION_ID}'::uuid
          );
    """)

