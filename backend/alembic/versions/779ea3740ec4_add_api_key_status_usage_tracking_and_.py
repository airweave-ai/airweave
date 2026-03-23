"""add api key status, usage tracking, and key prefix

Revision ID: 779ea3740ec4
Revises: f05f1fd46daa
Create Date: 2026-03-23 16:02:41.815331

"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "779ea3740ec4"
down_revision = "f05f1fd46daa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- api_key: new columns ---
    op.add_column(
        "api_key",
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
    )
    op.add_column(
        "api_key",
        sa.Column("last_used_date", sa.DateTime(timezone=False), nullable=True),
    )
    op.add_column(
        "api_key",
        sa.Column("last_used_ip", sa.String(), nullable=True),
    )
    op.add_column(
        "api_key",
        sa.Column("revoked_at", sa.DateTime(timezone=False), nullable=True),
    )
    op.add_column(
        "api_key",
        sa.Column("key_prefix", sa.String(12), nullable=True),
    )
    op.add_column(
        "api_key",
        sa.Column("key_hash", sa.String(64), nullable=True),
    )
    op.create_index("ix_api_key_key_hash", "api_key", ["key_hash"], unique=True)

    # --- api_key_usage_log: new table ---
    op.create_table(
        "api_key_usage_log",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("modified_at", sa.DateTime(), nullable=False),
        sa.Column(
            "api_key_id",
            sa.Uuid(),
            sa.ForeignKey("api_key.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("timestamp", sa.DateTime(timezone=False), nullable=False),
        sa.Column("ip_address", sa.String(), nullable=False),
        sa.Column("endpoint", sa.String(), nullable=False),
        sa.Column("user_agent", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_api_key_usage_log_key_ts",
        "api_key_usage_log",
        ["api_key_id", "timestamp"],
    )
    op.create_index(
        "ix_api_key_usage_log_org_ts",
        "api_key_usage_log",
        ["organization_id", "timestamp"],
    )


def downgrade() -> None:
    op.drop_index("ix_api_key_usage_log_org_ts", table_name="api_key_usage_log")
    op.drop_index("ix_api_key_usage_log_key_ts", table_name="api_key_usage_log")
    op.drop_table("api_key_usage_log")

    op.drop_index("ix_api_key_key_hash", table_name="api_key")
    op.drop_column("api_key", "key_hash")
    op.drop_column("api_key", "key_prefix")
    op.drop_column("api_key", "revoked_at")
    op.drop_column("api_key", "last_used_ip")
    op.drop_column("api_key", "last_used_date")
    op.drop_column("api_key", "status")
