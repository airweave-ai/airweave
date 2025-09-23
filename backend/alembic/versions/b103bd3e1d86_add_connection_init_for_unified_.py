"""add connection init for unified authentication flow

Revision ID: b103bd3e1d86
Revises: 0765a96ad189
Create Date: 2025-08-29 21:48:56.150687
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "b103bd3e1d86"
down_revision = "0765a96ad189"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "connection_init_session",
        sa.Column("short_name", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("overrides", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("final_connection_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "modified_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["final_connection_id"], ["connection.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_connection_init_session_state"),
        "connection_init_session",
        ["state"],
        unique=True,
    )
    op.create_index(
        "ix_connection_init_session_expires_at",
        "connection_init_session",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_connection_init_session_organization_id",
        "connection_init_session",
        ["organization_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_connection_init_session_organization_id", table_name="connection_init_session"
    )
    op.drop_index("ix_connection_init_session_expires_at", table_name="connection_init_session")
    op.drop_index(op.f("ix_connection_init_session_state"), table_name="connection_init_session")
    op.drop_table("connection_init_session")
