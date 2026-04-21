"""add source_hash and content_hash to entity

Revision ID: 0001
Revises: 0000
Create Date: 2026-04-21

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = "0000"
branch_labels = None
depends_on = None


def upgrade():
    # ADD COLUMN ... NULL is metadata-only in PostgreSQL — instant, no table rewrite.
    op.add_column(
        "entity",
        sa.Column(
            "source_hash",
            sa.String(),
            nullable=True,
            comment="Prefixed source-native content hash (e.g. sha256:e3b0c44...) for download-skip",
        ),
    )
    op.add_column(
        "entity",
        sa.Column(
            "content_hash",
            sa.String(),
            nullable=True,
            comment="SHA256 hex digest of file content bytes, reused when source_hash matches",
        ),
    )

    # CREATE INDEX CONCURRENTLY to avoid locking the (potentially huge) entity table.
    # CONCURRENTLY cannot run inside a transaction, so use autocommit_block.
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "idx_entity_sync_id_entity_id_source_hash "
            "ON entity (sync_id, entity_id, entity_definition_short_name, source_hash)"
        )


def downgrade():
    op.drop_index("idx_entity_sync_id_entity_id_source_hash", table_name="entity")
    op.drop_column("entity", "content_hash")
    op.drop_column("entity", "source_hash")
