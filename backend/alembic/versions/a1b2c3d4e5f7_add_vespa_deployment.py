"""Add vector_db_deployment_metadata table and migrate collection FK.

Revision ID: a1b2c3d4e5f7
Revises: r4s5t6u7v8w9
Create Date: 2026-02-23 00:00:00.000000

"""

import os
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f7"
down_revision = "r4s5t6u7v8w9"
branch_labels = None
depends_on = None

# Deterministic UUID so the seed row is predictable across environments
SEED_ID = uuid.UUID("00000000-0000-4000-a000-000000000001")


def upgrade() -> None:
    """Create vector_db_deployment_metadata, seed it from .env, migrate collection FK, drop old columns.

    Reads DENSE_EMBEDDER, EMBEDDING_DIMENSIONS, and SPARSE_EMBEDDER from the
    environment so the seed row matches whatever the operator configured in .env.
    """
    # These are guaranteed to be present: validate_embedding_config_sync()
    # runs in the DI container factory *before* Alembic migrations.
    dense_embedder = os.environ["DENSE_EMBEDDER"]
    embedding_dimensions = int(os.environ["EMBEDDING_DIMENSIONS"])
    sparse_embedder = os.environ["SPARSE_EMBEDDER"]

    # 1. Create vector_db_deployment_metadata table with singleton constraint
    op.create_table(
        "vector_db_deployment_metadata",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("modified_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "singleton",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            unique=True,
        ),
        sa.Column("dense_embedder", sa.String(), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False),
        sa.Column("sparse_embedder", sa.String(), nullable=False),
        sa.CheckConstraint("singleton = true", name="ck_vector_db_deployment_metadata_singleton"),
    )

    # 2. Seed a single row from the user's .env configuration
    op.execute(
        sa.text(
            "INSERT INTO vector_db_deployment_metadata "
            "(id, created_at, modified_at, singleton, "
            "dense_embedder, embedding_dimensions, sparse_embedder) "
            "VALUES (:id, NOW(), NOW(), true, :dense, :dims, :sparse)"
        ).bindparams(
            id=str(SEED_ID),
            dense=dense_embedder,
            dims=embedding_dimensions,
            sparse=sparse_embedder,
        )
    )

    # 3. Add vector_db_deployment_metadata_id column (nullable initially for backfill)
    op.add_column(
        "collection",
        sa.Column("vector_db_deployment_metadata_id", UUID, nullable=True),
    )

    # 4. Backfill all existing collections to point to the seed row
    op.execute(
        sa.text(
            "UPDATE collection SET vector_db_deployment_metadata_id = :vd_id"
        ).bindparams(vd_id=str(SEED_ID))
    )

    # 5. Make vector_db_deployment_metadata_id NOT NULL and add FK constraint
    op.alter_column("collection", "vector_db_deployment_metadata_id", nullable=False)
    op.create_foreign_key(
        "fk_collection_vector_db_deployment_metadata_id",
        "collection",
        "vector_db_deployment_metadata",
        ["vector_db_deployment_metadata_id"],
        ["id"],
    )

    # 6. Drop old columns
    op.drop_column("collection", "vector_size")
    op.drop_column("collection", "embedding_model_name")


def downgrade() -> None:
    """Reverse: re-add columns, backfill, drop FK and vector_db_deployment_metadata table."""
    # 1. Re-add old columns (nullable initially)
    op.add_column(
        "collection",
        sa.Column("vector_size", sa.Integer(), nullable=True),
    )
    op.add_column(
        "collection",
        sa.Column("embedding_model_name", sa.String(), nullable=True),
    )

    # 2. Backfill from vector_db_deployment_metadata
    op.execute(
        sa.text(
            "UPDATE collection c "
            "SET vector_size = vd.embedding_dimensions, "
            "    embedding_model_name = vd.dense_embedder "
            "FROM vector_db_deployment_metadata vd "
            "WHERE c.vector_db_deployment_metadata_id = vd.id"
        )
    )

    # 3. Make old columns NOT NULL
    op.alter_column("collection", "vector_size", nullable=False)
    op.alter_column("collection", "embedding_model_name", nullable=False)

    # 4. Drop FK and column
    op.drop_constraint(
        "fk_collection_vector_db_deployment_metadata_id", "collection", type_="foreignkey"
    )
    op.drop_column("collection", "vector_db_deployment_metadata_id")

    # 5. Drop vector_db_deployment_metadata table
    op.drop_table("vector_db_deployment_metadata")
