"""drop transformer table and dag_node.transformer_id FK

Revision ID: d2e3f4g5h6i7
Revises: c1d2e3f4g5h6
Create Date: 2026-03-04 20:00:00.000000

"""

from alembic import op
from sqlalchemy import inspect

revision = "d2e3f4g5h6i7"
down_revision = "c1d2e3f4g5h6"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if "dag_node" in inspector.get_table_names():
        op.drop_constraint(
            "dag_node_transformer_id_fkey", "dag_node", type_="foreignkey"
        )
        op.drop_column("dag_node", "transformer_id")

    if "transformer" in inspector.get_table_names():
        op.drop_table("transformer")


def downgrade():
    raise NotImplementedError(
        "Downgrade not supported — transformer table was removed as dead code"
    )
