"""index usage log timestamp

Revision ID: c9991bb9a94f
Revises: 6d0b927a491b
Create Date: 2026-03-25 14:30:33.114889

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'c9991bb9a94f'
down_revision = '6d0b927a491b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_api_key_usage_log_timestamp",
        "api_key_usage_log",
        ["timestamp"],
    )


def downgrade() -> None:
    op.drop_index("ix_api_key_usage_log_timestamp", table_name="api_key_usage_log")
