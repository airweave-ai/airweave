"""add vector_size to collection

Revision ID: d702ba6de953
Revises: 8be89aca78a6
Create Date: 2025-10-29 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text
from datetime import datetime, timezone


# revision identifiers, used by Alembic.
revision = "d702ba6de953"
down_revision = "8be89aca78a6"
branch_labels = None
depends_on = None


# CRITICAL: This is when we switched from text-embedding-3-small (1536) to text-embedding-3-large (3072)
# Collections created BEFORE this timestamp use 1536-dim
# Collections created AFTER this timestamp use 3072-dim (or get_default_vector_size())
EMBEDDING_MODEL_SWITCH_DATE = datetime(2025, 10, 29, 0, 0, 0, tzinfo=timezone.utc)


def get_default_vector_size():
    """Get default vector size based on environment."""
    import os

    # If OpenAI API key is set, default to 3072 (text-embedding-3-large)
    # Otherwise default to 384 (MiniLM-L6-v2)
    return 3072 if os.getenv("OPENAI_API_KEY") else 384


def upgrade():
    """Add vector_size and embedding_model_name columns to collection table.

    Strategy:
    1. Add vector_size column with temporary default (0)
    2. Add embedding_model_name column with temporary default ('')
    3. Backfill both based on creation timestamp:
       - Collections created BEFORE Oct 29, 2025 00:00:00 UTC:
         → 1536-dim + text-embedding-3-small
       - Collections created AFTER that date:
         → 3072-dim + text-embedding-3-large (current default)
    4. Make both columns NOT NULL (remove defaults)

    This time-based approach is:
    - Simple and deterministic
    - No external dependencies (no Qdrant queries needed)
    - Works reliably in all environments
    - Accurate based on when the embedding model was switched
    """
    print("\n" + "="*80)
    print("MIGRATION: Adding vector_size and embedding_model_name to collection table")
    print("="*80)
    print(f"\nEmbedding model switch date: {EMBEDDING_MODEL_SWITCH_DATE}")
    print(f"  - Collections created BEFORE this date → 1536-dim (text-embedding-3-small)")
    print(f"  - Collections created AFTER this date  → 3072-dim (text-embedding-3-large)")

    # Step 1: Add columns with temporary defaults
    print("\n[Step 1] Adding vector_size and embedding_model_name columns...")
    op.add_column(
        "collection",
        sa.Column("vector_size", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "collection",
        sa.Column("embedding_model_name", sa.String(), nullable=False, server_default="")
    )
    print("✅ Columns added")

    # Step 2: Backfill existing collections based on creation timestamp
    print("\n[Step 2] Backfilling vector_size and embedding_model_name (time-based)...")
    conn = op.get_bind()

    # Get all existing collections with their creation timestamps
    result = conn.execute(text("SELECT id, readable_id, name, created_at FROM collection"))
    collections = list(result)

    if not collections:
        print("   No existing collections found - skipping backfill")
    else:
        print(f"   Found {len(collections)} existing collections to backfill")

        default_vector_size = get_default_vector_size()
        print(f"   Current default vector size: {default_vector_size}")

        old_count = 0
        new_count = 0

        for collection_id, readable_id, name, created_at in collections:
            # Ensure created_at is timezone-aware for comparison
            # Database stores UTC timestamps but may return them as naive
            if created_at.tzinfo is None:
                created_at_aware = created_at.replace(tzinfo=timezone.utc)
            else:
                created_at_aware = created_at

            # Determine vector size and model name based on creation date
            if created_at_aware < EMBEDDING_MODEL_SWITCH_DATE:
                # Old collection - uses small embedding model
                vector_size = 1536
                embedding_model_name = "text-embedding-3-small"
                old_count += 1
                age_indicator = "OLD"
            else:
                # New collection - uses current default (large embedding model)
                vector_size = default_vector_size
                if vector_size == 3072:
                    embedding_model_name = "text-embedding-3-large"
                elif vector_size == 1536:
                    embedding_model_name = "text-embedding-3-small"
                else:
                    # 384 or other sizes
                    embedding_model_name = "sentence-transformers/all-MiniLM-L6-v2"
                new_count += 1
                age_indicator = "NEW"

            print(f"   {age_indicator} - {readable_id}: {vector_size}-dim ({embedding_model_name}, created: {created_at})")

            # Update the collection with both fields
            conn.execute(
                text("UPDATE collection SET vector_size = :size, embedding_model_name = :model WHERE id = :id"),
                {"size": vector_size, "model": embedding_model_name, "id": collection_id}
            )

        print(f"\n   ✅ Backfilled {len(collections)} collections:")
        print(f"      - {old_count} old collections → 1536-dim (text-embedding-3-small)")
        print(f"      - {new_count} new collections → {default_vector_size}-dim")

    # Step 3: Remove temporary defaults (make them true NOT NULL columns)
    print("\n[Step 3] Removing temporary defaults (finalizing schema)...")
    op.alter_column(
        "collection",
        "vector_size",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=None,  # Remove default
    )
    op.alter_column(
        "collection",
        "embedding_model_name",
        existing_type=sa.String(),
        nullable=False,
        server_default=None,  # Remove default
    )
    print("✅ Columns finalized as NOT NULL")

    print("\n" + "="*80)
    print("✅ MIGRATION COMPLETE")
    print("="*80)
    print("\nSummary:")
    print(f"  - Added vector_size and embedding_model_name columns to collection table")
    print(f"  - Backfilled {len(collections) if collections else 0} existing collections based on creation date")
    print(f"  - Old collections (< {EMBEDDING_MODEL_SWITCH_DATE}): 1536-dim + text-embedding-3-small")
    print(f"  - New collections (>= {EMBEDDING_MODEL_SWITCH_DATE}): {get_default_vector_size()}-dim + appropriate model")
    print(f"  - Future collections will determine vector_size and model at creation time")
    print("\n")


def downgrade():
    """Remove vector_size and embedding_model_name columns from collection table."""
    print("\n⚠️  WARNING: Downgrading - removing vector_size and embedding_model_name columns")
    print("   This will lose information about which embedding model each collection uses!")

    op.drop_column("collection", "embedding_model_name")
    op.drop_column("collection", "vector_size")

    print("✅ Columns removed (not recommended for production)")
