"""Remove Qdrant native destination from all syncs and connections.

Revision ID: q3r4s5t6u7v8
Revises: p2q3r4s5t6u7
Create Date: 2026-02-09 12:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "q3r4s5t6u7v8"
down_revision = "p2q3r4s5t6u7"
branch_labels = None
depends_on = None

# Native destination connection UUIDs (must match core/constants/reserved_ids.py)
QDRANT_CONNECTION_ID = "11111111-1111-1111-1111-111111111111"
VESPA_CONNECTION_ID = "33333333-3333-3333-3333-333333333333"


def upgrade():
    """Remove all Qdrant sync_connection rows and the native Qdrant connection.

    Phase 2 of Qdrant deprecation: after Phase 1 stopped all writes to Qdrant,
    this migration cleans up the database references.
    """
    # 1. Remove all sync_connection rows pointing to the native Qdrant destination
    op.execute(f"""
        DELETE FROM sync_connection
        WHERE connection_id = '{QDRANT_CONNECTION_ID}'::uuid;
    """)

    # 2. Remove the native Qdrant connection row itself
    op.execute(f"""
        DELETE FROM connection
        WHERE id = '{QDRANT_CONNECTION_ID}'::uuid
          AND short_name = 'qdrant_native';
    """)


def downgrade():
    """Re-insert the native Qdrant connection and restore sync_connection rows.

    Restores Qdrant as a destination for all syncs that currently have Vespa,
    matching the state before Phase 2 deprecation.
    """
    # 1. Re-insert the native Qdrant connection
    op.execute(f"""
        INSERT INTO connection (id, name, readable_id, integration_type, short_name, status, created_at, modified_at)
        VALUES (
            '{QDRANT_CONNECTION_ID}'::uuid,
            'Native Qdrant',
            'native-qdrant',
            'DESTINATION',
            'qdrant_native',
            'ACTIVE',
            NOW(),
            NOW()
        )
        ON CONFLICT (id) DO NOTHING;
    """)

    # 2. Re-insert sync_connection rows for all syncs that have Vespa
    #    (mirrors the state before deprecation when all syncs had both)
    op.execute(f"""
        INSERT INTO sync_connection (id, sync_id, connection_id, created_at, modified_at)
        SELECT
            gen_random_uuid(),
            sc.sync_id,
            '{QDRANT_CONNECTION_ID}'::uuid,
            NOW(),
            NOW()
        FROM sync_connection sc
        WHERE sc.connection_id = '{VESPA_CONNECTION_ID}'::uuid
          AND NOT EXISTS (
            SELECT 1
            FROM sync_connection sc2
            WHERE sc2.sync_id = sc.sync_id
              AND sc2.connection_id = '{QDRANT_CONNECTION_ID}'::uuid
          );
    """)
