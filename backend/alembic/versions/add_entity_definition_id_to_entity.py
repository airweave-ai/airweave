"""Add entity_definition_id to entity table

Revision ID: add_entity_definition_id
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "add_entity_definition_id"
down_revision: Union[str, None] = "0765a96ad189"  # Latest migration head
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add entity_definition_id column to entity table
    op.add_column(
        "entity",
        sa.Column(
            "entity_definition_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,  # Initially nullable for existing records
            comment="Entity definition this entity belongs to",
        ),
    )

    # Add foreign key constraint
    op.create_foreign_key(
        "fk_entity_entity_definition_id",
        "entity",
        "entity_definition",
        ["entity_definition_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Create indexes for performance
    op.create_index("idx_entity_entity_definition_id", "entity", ["entity_definition_id"])
    op.create_index(
        "idx_entity_sync_id_entity_def_id", "entity", ["sync_id", "entity_definition_id"]
    )

    # TODO: After deployment, run a data migration to populate entity_definition_id
    # for existing records based on the entity type, then make the column NOT NULL


def downgrade() -> None:
    # Drop indexes
    op.drop_index("idx_entity_sync_id_entity_def_id", table_name="entity")
    op.drop_index("idx_entity_entity_definition_id", table_name="entity")

    # Drop foreign key constraint
    op.drop_constraint("fk_entity_entity_definition_id", "entity", type_="foreignkey")

    # Drop column
    op.drop_column("entity", "entity_definition_id")
