"""Add collection_id to entity table for collection-level deduplication.

Revision ID: o8p9q0r1s2t3
Revises: n7o8p9q0r1s2
Create Date: 2026-01-10 16:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "o8p9q0r1s2t3"
down_revision = "n7o8p9q0r1s2"
branch_labels = None
depends_on = None


def upgrade():
    """Add collection_id column and partial index for collection-level dedup."""
    # Add collection_id column (nullable for backward compatibility)
    op.add_column(
        "entity",
        sa.Column(
            "collection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("collection.id", ondelete="CASCADE", name="fk_entity_collection_id"),
            nullable=True,
            comment="Collection ID for collection-level deduplication (optional)",
        ),
    )

    # Add partial composite index for collection-level dedup lookups
    # Only indexes rows where collection_id IS NOT NULL (partial index)
    op.create_index(
        "idx_entity_collection_entity_def",
        "entity",
        ["collection_id", "entity_id", "entity_definition_id"],
        postgresql_where=sa.text("collection_id IS NOT NULL"),
    )


def downgrade():
    """Remove collection_id column and index."""
    op.drop_index("idx_entity_collection_entity_def", table_name="entity")
    op.drop_column("entity", "collection_id")
