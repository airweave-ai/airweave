"""Add entity count table and triggers

Revision ID: add_entity_count
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "add_entity_count"
down_revision: Union[str, None] = (
    "add_entity_definition_id"  # Depends on entity_definition_id migration
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create entity_count table
    op.create_table(
        "entity_count",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "modified_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("sync_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "entity_definition_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("count", sa.Integer(), nullable=False, default=0),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["sync_id"], ["sync.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["entity_definition_id"], ["entity_definition.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("sync_id", "entity_definition_id", name="uq_sync_entity_definition"),
    )

    # Create indexes for performance
    op.create_index("idx_entity_count_sync_id", "entity_count", ["sync_id"])
    op.create_index("idx_entity_count_entity_def_id", "entity_count", ["entity_definition_id"])
    op.create_index(
        "idx_entity_count_sync_def", "entity_count", ["sync_id", "entity_definition_id"]
    )

    # Create trigger function to update counts
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_entity_count()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Skip if entity_definition_id is NULL (legacy entities)
            IF TG_OP = 'INSERT' AND NEW.entity_definition_id IS NULL THEN
                RETURN NEW;
            END IF;
            IF TG_OP = 'DELETE' AND OLD.entity_definition_id IS NULL THEN
                RETURN OLD;
            END IF;
            IF TG_OP = 'UPDATE' AND (NEW.entity_definition_id IS NULL OR OLD.entity_definition_id IS NULL) THEN
                RETURN NEW;
            END IF;

            IF TG_OP = 'INSERT' THEN
                -- Use entity_definition_id directly
                INSERT INTO entity_count (sync_id, entity_definition_id, count, created_at, modified_at)
                VALUES (
                    NEW.sync_id,
                    NEW.entity_definition_id,
                    1,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT (sync_id, entity_definition_id)
                DO UPDATE SET
                    count = entity_count.count + 1,
                    modified_at = CURRENT_TIMESTAMP;

            ELSIF TG_OP = 'DELETE' THEN
                UPDATE entity_count
                SET count = GREATEST(0, count - 1),
                    modified_at = CURRENT_TIMESTAMP
                WHERE sync_id = OLD.sync_id
                  AND entity_definition_id = OLD.entity_definition_id;

                -- Clean up zero counts (optional)
                DELETE FROM entity_count
                WHERE sync_id = OLD.sync_id
                  AND entity_definition_id = OLD.entity_definition_id
                  AND count = 0;

            ELSIF TG_OP = 'UPDATE' THEN
                -- Handle updates if sync_id or entity_definition_id changes
                IF OLD.sync_id != NEW.sync_id OR OLD.entity_definition_id != NEW.entity_definition_id THEN
                    -- Decrement old
                    UPDATE entity_count
                    SET count = GREATEST(0, count - 1),
                        modified_at = CURRENT_TIMESTAMP
                    WHERE sync_id = OLD.sync_id
                      AND entity_definition_id = OLD.entity_definition_id;

                    -- Increment new
                    INSERT INTO entity_count (sync_id, entity_definition_id, count, created_at, modified_at)
                    VALUES (
                        NEW.sync_id,
                        NEW.entity_definition_id,
                        1,
                        CURRENT_TIMESTAMP,
                        CURRENT_TIMESTAMP
                    )
                    ON CONFLICT (sync_id, entity_definition_id)
                    DO UPDATE SET
                        count = entity_count.count + 1,
                        modified_at = CURRENT_TIMESTAMP;
                END IF;
            END IF;

            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            ELSE
                RETURN NEW;
            END IF;
        END;
        $$ LANGUAGE plpgsql;
    """
    )

    # Create trigger on entity table
    op.execute(
        """
        CREATE TRIGGER entity_count_trigger
        AFTER INSERT OR UPDATE OR DELETE ON entity
        FOR EACH ROW
        EXECUTE FUNCTION update_entity_count();
    """
    )

    # Initialize counts from existing data
    op.execute(
        """
        INSERT INTO entity_count (sync_id, entity_definition_id, count, created_at, modified_at)
        SELECT
            sync_id,
            entity_definition_id,
            COUNT(*) as count,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        FROM entity
        WHERE entity_definition_id IS NOT NULL
        GROUP BY sync_id, entity_definition_id
        ON CONFLICT (sync_id, entity_definition_id) DO NOTHING;
    """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS update_entity_count() CASCADE")
    op.execute("DROP TRIGGER IF EXISTS entity_count_trigger ON entity CASCADE")
    op.drop_index("idx_entity_count_sync_def", table_name="entity_count CASCADE")
    op.drop_index("idx_entity_count_entity_def_id", table_name="entity_count CASCADE")
    op.drop_index("idx_entity_count_sync_id", table_name="entity_count CASCADE")
    op.drop_table("entity_count")
