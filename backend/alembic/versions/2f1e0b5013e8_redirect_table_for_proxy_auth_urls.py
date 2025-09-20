"""redirect table for proxy auth urls

Revision ID: 2f1e0b5013e8
Revises: b103bd3e1d86
Create Date: 2025-08-30 17:07:56.265007
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "2f1e0b5013e8"
down_revision = "b103bd3e1d86"
branch_labels = None
depends_on = None


def upgrade():
    # Create redirect_session (ephemeral one-time redirect mapping)
    op.create_table(
        "redirect_session",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "modified_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("final_url", sa.Text(), nullable=False),
        sa.Column("expires_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("redirect_session_organization_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("redirect_session_pkey")),
        sa.UniqueConstraint("code", name=op.f("uq_redirect_session_code")),
    )
    # Helpful secondary indexes
    op.create_index(
        op.f("ix_redirect_session_organization_id"),
        "redirect_session",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_redirect_session_expires_at"),
        "redirect_session",
        ["expires_at"],
        unique=False,
    )


def downgrade():
    # Drop indexes then table
    op.drop_index(op.f("ix_redirect_session_expires_at"), table_name="redirect_session")
    op.drop_index(op.f("ix_redirect_session_organization_id"), table_name="redirect_session")
    op.drop_table("redirect_session")
