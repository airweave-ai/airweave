"""drop pg_field_catalog tables and polymorphic entity definition

Revision ID: r4s5t6u7v8w9
Revises: j3k4l5m6n7o8, q3r4s5t6u7v8
Create Date: 2026-02-12 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "r4s5t6u7v8w9"
down_revision = ("j3k4l5m6n7o8", "q3r4s5t6u7v8")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop pg_field_catalog tables (column table has FK to table table, drop first)
    op.drop_table("pg_field_catalog_column")
    op.drop_table("pg_field_catalog_table")

    # Remove the reserved polymorphic entity definition row
    op.execute(
        "DELETE FROM entity_definition WHERE id = '11111111-1111-1111-1111-111111111111'"
    )


def downgrade() -> None:
    # Re-insert the reserved polymorphic entity definition
    op.execute(
        """
        INSERT INTO entity_definition (id, name, description, type, entity_schema, module_name, class_name)
        VALUES (
            '11111111-1111-1111-1111-111111111111',
            'Polymorphic Table Entity',
            'Base entity type for polymorphic table entities',
            'json',
            '{}',
            'airweave.platform.entities.polymorphic',
            'PolymorphicEntity'
        )
        """
    )

    # Recreate pg_field_catalog_table
    op.create_table(
        "pg_field_catalog_table",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("modified_at", sa.DateTime(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("source_connection_id", sa.UUID(), nullable=False),
        sa.Column("schema_name", sa.String(), nullable=False),
        sa.Column("table_name", sa.String(), nullable=False),
        sa.Column("recency_column", sa.String(), nullable=True),
        sa.Column("primary_keys", sa.JSON(), nullable=True),
        sa.Column("foreign_keys", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_connection_id"], ["source_connection.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "source_connection_id",
            "schema_name",
            "table_name",
            name="uq_pg_field_catalog_table_scope",
        ),
    )

    # Recreate pg_field_catalog_column
    op.create_table(
        "pg_field_catalog_column",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("modified_at", sa.DateTime(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("table_id", sa.UUID(), nullable=False),
        sa.Column("column_name", sa.String(), nullable=False),
        sa.Column("data_type", sa.String(), nullable=True),
        sa.Column("udt_name", sa.String(), nullable=True),
        sa.Column("is_nullable", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("default_value", sa.String(), nullable=True),
        sa.Column("ordinal_position", sa.Integer(), nullable=True),
        sa.Column("is_primary_key", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("is_foreign_key", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("ref_schema", sa.String(), nullable=True),
        sa.Column("ref_table", sa.String(), nullable=True),
        sa.Column("ref_column", sa.String(), nullable=True),
        sa.Column("enum_values", sa.JSON(), nullable=True),
        sa.Column("is_filterable", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["table_id"], ["pg_field_catalog_table.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("table_id", "column_name", name="uq_pg_field_catalog_column_name"),
    )
