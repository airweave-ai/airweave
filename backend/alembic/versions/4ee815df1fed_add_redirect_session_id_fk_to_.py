"""Add redirect_session_id FK to connection_init_session

Revision ID: 4ee815df1fed
Revises: a803b8e613be
Create Date: 2025-09-22 18:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "4ee815df1fed"
down_revision: Union[str, None] = "b1d1597dbcdb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add the redirect_session_id column
    op.add_column(
        "connection_init_session",
        sa.Column("redirect_session_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Add foreign key constraint
    op.create_foreign_key(
        "fk_connection_init_session_redirect_session_id",
        "connection_init_session",
        "redirect_session",
        ["redirect_session_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Add index for better query performance
    op.create_index(
        "idx_connection_init_session_redirect_session_id",
        "connection_init_session",
        ["redirect_session_id"],
    )


def downgrade() -> None:
    # Drop index
    op.drop_index("idx_connection_init_session_redirect_session_id", "connection_init_session")

    # Drop foreign key constraint
    op.drop_constraint(
        "fk_connection_init_session_redirect_session_id",
        "connection_init_session",
        type_="foreignkey",
    )

    # Drop the column
    op.drop_column("connection_init_session", "redirect_session_id")
