"""session schema hardening

Revision ID: a2b3c4d5e6f7
Revises: 01991ee09f59
Create Date: 2026-04-02 12:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "a2b3c4d5e6f7"
down_revision = "01991ee09f59"
branch_labels = None
depends_on = None


def upgrade() -> None:  # noqa: D103
    op.alter_column(
        "user_session",
        "user_agent",
        existing_type=sa.String(),
        type_=sa.String(512),
        existing_nullable=True,
    )
    op.create_index(
        "ix_user_session_user_id_is_revoked",
        "user_session",
        ["user_id", "is_revoked"],
    )


def downgrade() -> None:  # noqa: D103
    op.drop_index("ix_user_session_user_id_is_revoked", table_name="user_session")
    op.alter_column(
        "user_session",
        "user_agent",
        existing_type=sa.String(512),
        type_=sa.String(),
        existing_nullable=True,
    )
