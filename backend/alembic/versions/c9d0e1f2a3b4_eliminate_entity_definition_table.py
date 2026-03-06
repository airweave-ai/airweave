"""Eliminate entity_definition table — migrate to registry short_name strings.

Replaces entity_definition_id (UUID FK) with entity_definition_short_name (String)
on entity, entity_count, and entity_relation tables. Backfills from the JOIN,
updates the PostgreSQL trigger, then drops the entity_definition table.

Revision ID: c9d0e1f2a3b4
Revises: b788750e60fe
Create Date: 2026-03-03 00:00:00.000000
"""

from typing import List, Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "b788750e60fe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _get_fk_constraint_names(table: str, column: str) -> List[str]:
    """Look up FK constraint names from pg_constraint for a given table/column."""
    conn = op.get_bind()
    rows = conn.execute(sa.text("""
        SELECT con.conname
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
        JOIN pg_attribute att ON att.attrelid = con.conrelid
                              AND att.attnum = ANY(con.conkey)
        WHERE rel.relname = :table
          AND att.attname = :column
          AND con.contype = 'f'
          AND nsp.nspname = 'public'
    """), {"table": table, "column": column})
    return [row[0] for row in rows]


def _drop_fk_constraints(table: str, column: str) -> None:
    """Drop all FK constraints on table.column, looked up dynamically."""
    for name in _get_fk_constraint_names(table, column):
        op.drop_constraint(name, table, type_="foreignkey")


def _to_snake_case_sql() -> str:
    """SQL expression to convert PascalCase entity_definition.name to snake_case."""
    return """
        lower(
            regexp_replace(
                regexp_replace(name, '([a-z0-9])([A-Z])', '\\1_\\2', 'g'),
                '([A-Z])([A-Z][a-z])', '\\1_\\2', 'g'
            )
        )
    """


def upgrade() -> None:
    # ---------------------------------------------------------------
    # 1. Add new string columns (nullable for now)
    # ---------------------------------------------------------------
    op.add_column(
        "entity",
        sa.Column("entity_definition_short_name", sa.String(), nullable=True),
    )
    op.add_column(
        "entity_count",
        sa.Column("entity_definition_short_name", sa.String(), nullable=True),
    )
    op.add_column(
        "entity_relation",
        sa.Column("from_entity_definition_short_name", sa.String(), nullable=True),
    )
    op.add_column(
        "entity_relation",
        sa.Column("to_entity_definition_short_name", sa.String(), nullable=True),
    )

    # ---------------------------------------------------------------
    # 2. Backfill from entity_definition table via JOIN
    # ---------------------------------------------------------------
    snake = _to_snake_case_sql()

    op.execute(f"""
        UPDATE entity e
        SET entity_definition_short_name = (
            SELECT {snake}
            FROM entity_definition ed
            WHERE ed.id = e.entity_definition_id
        )
        WHERE e.entity_definition_id IS NOT NULL
          AND e.entity_definition_short_name IS NULL
    """)

    op.execute(f"""
        UPDATE entity_count ec
        SET entity_definition_short_name = (
            SELECT {snake}
            FROM entity_definition ed
            WHERE ed.id = ec.entity_definition_id
        )
        WHERE ec.entity_definition_short_name IS NULL
    """)

    op.execute(f"""
        UPDATE entity_relation er
        SET from_entity_definition_short_name = (
            SELECT {snake}
            FROM entity_definition ed
            WHERE ed.id = er.from_entity_definition_id
        ),
        to_entity_definition_short_name = (
            SELECT {snake}
            FROM entity_definition ed
            WHERE ed.id = er.to_entity_definition_id
        )
        WHERE er.from_entity_definition_short_name IS NULL
           OR er.to_entity_definition_short_name IS NULL
    """)

    # ---------------------------------------------------------------
    # 2b. Validate backfill — abort before NOT NULL if orphans remain
    # ---------------------------------------------------------------
    conn = op.get_bind()

    orphan_ec = conn.execute(sa.text(
        "SELECT count(*) FROM entity_count "
        "WHERE entity_definition_short_name IS NULL"
    )).scalar()
    if orphan_ec:
        raise RuntimeError(
            f"Backfill incomplete: {orphan_ec} entity_count rows still have "
            "NULL entity_definition_short_name (orphaned entity_definition FK?). "
            "Fix data before re-running migration."
        )

    orphan_er_from = conn.execute(sa.text(
        "SELECT count(*) FROM entity_relation "
        "WHERE from_entity_definition_short_name IS NULL"
    )).scalar()
    orphan_er_to = conn.execute(sa.text(
        "SELECT count(*) FROM entity_relation "
        "WHERE to_entity_definition_short_name IS NULL"
    )).scalar()
    if orphan_er_from or orphan_er_to:
        raise RuntimeError(
            f"Backfill incomplete: entity_relation has "
            f"{orphan_er_from} NULL from / {orphan_er_to} NULL to short names. "
            "Fix data before re-running migration."
        )

    # ---------------------------------------------------------------
    # 3. Drop old FK constraints and UUID columns
    # ---------------------------------------------------------------

    # entity table
    op.drop_constraint("uq_sync_id_entity_id_entity_definition_id", "entity", type_="unique")
    _drop_fk_constraints("entity", "entity_definition_id")
    op.drop_index("idx_entity_entity_definition_id", table_name="entity")
    op.drop_index("idx_entity_sync_id_entity_def_id", table_name="entity")
    op.drop_column("entity", "entity_definition_id")

    # entity_count table
    op.drop_constraint("uq_sync_entity_definition", "entity_count", type_="unique")
    _drop_fk_constraints("entity_count", "entity_definition_id")
    op.drop_index("idx_entity_count_entity_def_id", table_name="entity_count")
    op.drop_column("entity_count", "entity_definition_id")

    # entity_relation table
    op.drop_constraint("uq_entity_relation", "entity_relation", type_="unique")
    op.drop_index("idx_entity_relation_from", table_name="entity_relation")
    op.drop_index("idx_entity_relation_to", table_name="entity_relation")
    _drop_fk_constraints("entity_relation", "from_entity_definition_id")
    _drop_fk_constraints("entity_relation", "to_entity_definition_id")
    op.drop_column("entity_relation", "from_entity_definition_id")
    op.drop_column("entity_relation", "to_entity_definition_id")

    # ---------------------------------------------------------------
    # 4. Create new constraints and indexes on string columns
    # ---------------------------------------------------------------

    # entity
    op.create_unique_constraint(
        "uq_sync_id_entity_id_entity_def_short_name",
        "entity",
        ["sync_id", "entity_id", "entity_definition_short_name"],
    )
    op.create_index(
        "idx_entity_entity_def_short_name",
        "entity",
        ["entity_definition_short_name"],
    )
    op.create_index(
        "idx_entity_sync_id_entity_def_short_name",
        "entity",
        ["sync_id", "entity_definition_short_name"],
    )

    # entity_count
    op.alter_column("entity_count", "entity_definition_short_name", nullable=False)
    op.create_unique_constraint(
        "uq_sync_entity_def_short_name",
        "entity_count",
        ["sync_id", "entity_definition_short_name"],
    )
    op.create_index(
        "idx_entity_count_entity_def_short_name",
        "entity_count",
        ["entity_definition_short_name"],
    )

    # entity_relation
    op.alter_column("entity_relation", "from_entity_definition_short_name", nullable=False)
    op.alter_column("entity_relation", "to_entity_definition_short_name", nullable=False)
    op.create_unique_constraint(
        "uq_entity_relation",
        "entity_relation",
        [
            "from_entity_definition_short_name",
            "to_entity_definition_short_name",
            "name",
            "organization_id",
        ],
    )
    op.create_index(
        "idx_entity_relation_from",
        "entity_relation",
        ["from_entity_definition_short_name"],
    )
    op.create_index(
        "idx_entity_relation_to",
        "entity_relation",
        ["to_entity_definition_short_name"],
    )

    # ---------------------------------------------------------------
    # 5. Replace the trigger to use entity_definition_short_name
    # ---------------------------------------------------------------
    op.execute("DROP TRIGGER IF EXISTS entity_count_trigger ON entity")
    op.execute("DROP FUNCTION IF EXISTS update_entity_count()")

    op.execute("""
        CREATE OR REPLACE FUNCTION update_entity_count()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' AND NEW.entity_definition_short_name IS NULL THEN
                RETURN NEW;
            END IF;
            IF TG_OP = 'DELETE' AND OLD.entity_definition_short_name IS NULL THEN
                RETURN OLD;
            END IF;
            IF TG_OP = 'UPDATE' AND (
                NEW.entity_definition_short_name IS NULL
                OR OLD.entity_definition_short_name IS NULL
            ) THEN
                RETURN NEW;
            END IF;

            IF TG_OP = 'INSERT' THEN
                INSERT INTO entity_count (
                    sync_id, entity_definition_short_name, count,
                    created_at, modified_at
                )
                VALUES (
                    NEW.sync_id, NEW.entity_definition_short_name, 1,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                ON CONFLICT (sync_id, entity_definition_short_name)
                DO UPDATE SET
                    count = entity_count.count + 1,
                    modified_at = CURRENT_TIMESTAMP;

            ELSIF TG_OP = 'DELETE' THEN
                UPDATE entity_count
                SET count = GREATEST(0, count - 1),
                    modified_at = CURRENT_TIMESTAMP
                WHERE sync_id = OLD.sync_id
                  AND entity_definition_short_name = OLD.entity_definition_short_name;

                DELETE FROM entity_count
                WHERE sync_id = OLD.sync_id
                  AND entity_definition_short_name = OLD.entity_definition_short_name
                  AND count = 0;

            ELSIF TG_OP = 'UPDATE' THEN
                IF OLD.sync_id != NEW.sync_id
                   OR OLD.entity_definition_short_name != NEW.entity_definition_short_name
                THEN
                    UPDATE entity_count
                    SET count = GREATEST(0, count - 1),
                        modified_at = CURRENT_TIMESTAMP
                    WHERE sync_id = OLD.sync_id
                      AND entity_definition_short_name = OLD.entity_definition_short_name;

                    INSERT INTO entity_count (
                        sync_id, entity_definition_short_name, count,
                        created_at, modified_at
                    )
                    VALUES (
                        NEW.sync_id, NEW.entity_definition_short_name, 1,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    ON CONFLICT (sync_id, entity_definition_short_name)
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
    """)

    op.execute("""
        CREATE TRIGGER entity_count_trigger
        AFTER INSERT OR UPDATE OR DELETE ON entity
        FOR EACH ROW
        EXECUTE FUNCTION update_entity_count();
    """)

    # ---------------------------------------------------------------
    # 6. Drop the entity_definition table
    # ---------------------------------------------------------------
    op.drop_table("entity_definition")


def downgrade() -> None:
    raise NotImplementedError(
        "Downgrade not supported — entity_definition data has been dropped. "
        "Restore from backup if needed."
    )
