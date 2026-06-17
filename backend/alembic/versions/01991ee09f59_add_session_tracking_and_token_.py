"""add session tracking and token revocation

Revision ID: 01991ee09f59
Revises: 9a0ad1e89bbe
Create Date: 2026-04-01 17:36:09.157842

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "01991ee09f59"
down_revision = "9a0ad1e89bbe"
branch_labels = None
depends_on = None


def upgrade() -> None:  # noqa: D103
    op.add_column("user", sa.Column("tokens_revoked_at", sa.DateTime(), nullable=True))

    op.create_table(
        "user_session",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("last_active_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("modified_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_session_user_id"), "user_session", ["user_id"])
    op.create_index(op.f("ix_user_session_session_id"), "user_session", ["session_id"], unique=True)


def downgrade() -> None:  # noqa: D103
    op.drop_index(op.f("ix_user_session_session_id"), table_name="user_session")
    op.drop_index(op.f("ix_user_session_user_id"), table_name="user_session")
    op.drop_table("user_session")
    op.drop_column("user", "tokens_revoked_at")
