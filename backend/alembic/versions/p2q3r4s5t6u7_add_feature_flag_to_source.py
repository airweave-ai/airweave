"""Add feature_flag column to source table.

Revision ID: p2q3r4s5t6u7
Revises: o1p2q3r4s5t6
Create Date: 2026-01-27 12:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "p2q3r4s5t6u7"
down_revision = "o1p2q3r4s5t6"
branch_labels = None
depends_on = None


def upgrade():
    """Add feature_flag column to source table.

    This column allows sources to be gated behind organization-level
    feature flags. When set, only organizations with the specified
    feature flag enabled can see and use this source.
    """
    op.add_column(
        "source",
        sa.Column(
            "feature_flag",
            sa.String(),
            nullable=True,
        ),
    )

    # Set feature flag for sharepoint2019v2
    op.execute(
        "UPDATE source SET feature_flag = 'sharepoint_2019_v2' "
        "WHERE short_name = 'sharepoint2019v2'"
    )


def downgrade():
    """Remove feature_flag column from source table."""
    op.drop_column("source", "feature_flag")

