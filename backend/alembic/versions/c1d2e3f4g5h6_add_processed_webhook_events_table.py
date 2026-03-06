"""add processed_webhook_event table for idempotent webhooks

Revision ID: c1d2e3f4g5h6
Revises: b788750e60fe
Create Date: 2026-03-04 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "c1d2e3f4g5h6"
down_revision = "b788750e60fe"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "processed_webhook_event",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("modified_at", sa.DateTime(), nullable=False),
        sa.Column("stripe_event_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_processed_webhook_event_stripe_event_id"),
        "processed_webhook_event",
        ["stripe_event_id"],
        unique=True,
    )


def downgrade():
    op.drop_index(
        op.f("ix_processed_webhook_event_stripe_event_id"),
        table_name="processed_webhook_event",
    )
    op.drop_table("processed_webhook_event")
