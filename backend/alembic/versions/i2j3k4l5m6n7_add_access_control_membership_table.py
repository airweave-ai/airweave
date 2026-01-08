"""Add access_control_membership table.

Revision ID: i2j3k4l5m6n7
Revises: h1i2j3k4l5m6
Create Date: 2026-01-05 12:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "i2j3k4l5m6n7"
down_revision = "h1i2j3k4l5m6"
branch_labels = None
depends_on = None


def upgrade():
    """Create access_control_membership table with clean tuple design.

    Tuple: (member_id, member_type) → group_id

    Examples:
    - User-to-group: ("john@acme.com", "user", "group-engineering")
    - Group-to-group: ("group-frontend", "group", "group-engineering")
    """
    op.create_table(
        "access_control_membership",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Member (the principal joining the group)
        sa.Column("member_id", sa.String(255), nullable=False),
        sa.Column("member_type", sa.String(10), nullable=False),
        # Parent group (the group being joined)
        sa.Column("group_id", sa.String(255), nullable=False),
        sa.Column("group_name", sa.String(255), nullable=True),
        # Source info
        sa.Column("source_name", sa.String(50), nullable=False),
        sa.Column("source_connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("modified_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"]),
        sa.ForeignKeyConstraint(
            ["source_connection_id"], ["source_connection.id"], ondelete="CASCADE"
        ),
    )

    # Create indexes for fast lookups
    # Composite index on member (used for all queries)
    op.create_index(
        "idx_acl_membership_member",
        "access_control_membership",
        ["organization_id", "member_id", "member_type"],
    )
    # Index on parent group
    op.create_index(
        "idx_acl_membership_group", "access_control_membership", ["organization_id", "group_id"]
    )
    # Index for cleanup by source
    op.create_index(
        "idx_acl_membership_source", "access_control_membership", ["source_connection_id"]
    )
    # Unique constraint on (org, member, group, source_connection)
    op.create_index(
        "uq_acl_membership",
        "access_control_membership",
        ["organization_id", "member_id", "member_type", "group_id", "source_connection_id"],
        unique=True,
    )


def downgrade():
    """Drop access_control_membership table."""
    op.drop_table("access_control_membership")
