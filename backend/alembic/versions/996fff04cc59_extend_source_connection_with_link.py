"""extend source connection with link

Revision ID: 996fff04cc59
Revises: 2f1e0b5013e8
Create Date: 2025-09-02 11:20:01.034365
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "996fff04cc59"
down_revision = "2f1e0b5013e8"
branch_labels = None
depends_on = None


def upgrade():
    # --- connection_init_session changes ---
    op.alter_column(
        "connection_init_session",
        "payload",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=sa.JSON(),
        existing_nullable=False,
    )
    op.alter_column(
        "connection_init_session",
        "overrides",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=sa.JSON(),
        existing_nullable=False,
    )
    op.alter_column(
        "connection_init_session",
        "created_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "connection_init_session",
        "modified_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.drop_index(
        op.f("ix_connection_init_session_expires_at"),
        table_name="connection_init_session",
    )
    op.drop_index(
        op.f("ix_connection_init_session_organization_id"),
        table_name="connection_init_session",
    )

    # --- source_connection additions ---
    op.add_column(
        "source_connection",
        sa.Column("connection_init_session_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "source_connection",
        sa.Column("is_authenticated", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_foreign_key(
        "fk_source_connection_connection_init_session_id",
        "source_connection",
        "connection_init_session",
        ["connection_init_session_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    # --- source_connection rollback ---
    op.drop_constraint(
        "fk_source_connection_connection_init_session_id",
        "source_connection",
        type_="foreignkey",
    )
    op.drop_column("source_connection", "is_authenticated")
    op.drop_column("source_connection", "connection_init_session_id")

    # --- connection_init_session rollback ---
    op.create_index(
        op.f("ix_connection_init_session_organization_id"),
        "connection_init_session",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_connection_init_session_expires_at"),
        "connection_init_session",
        ["expires_at"],
        unique=False,
    )
    op.alter_column(
        "connection_init_session",
        "modified_at",
        existing_type=sa.DateTime(),
        type_=postgresql.TIMESTAMP(timezone=True),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "connection_init_session",
        "created_at",
        existing_type=sa.DateTime(),
        type_=postgresql.TIMESTAMP(timezone=True),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "connection_init_session",
        "overrides",
        existing_type=sa.JSON(),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=False,
    )
    op.alter_column(
        "connection_init_session",
        "payload",
        existing_type=sa.JSON(),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=False,
    )
