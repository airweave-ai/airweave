"""Remove stale feature flags no longer defined in the FeatureFlag enum.

Cleans up database rows for flags that were removed from the codebase
(e.g. 'agentic_search') to prevent ValueError on enum coercion.

Revision ID: f05f1fd46daa
Revises: 7f3a9c2b1d4e
Create Date: 2026-03-21
"""

from alembic import op

from airweave.core.shared_models import FeatureFlag


revision = "f05f1fd46daa"
down_revision = "7f3a9c2b1d4e"
branch_labels = None
depends_on = None

KNOWN_FLAGS = {f.value for f in FeatureFlag}


def upgrade() -> None:
    quoted = ", ".join(f"'{v}'" for v in KNOWN_FLAGS)
    op.execute(f"DELETE FROM feature_flag WHERE flag NOT IN ({quoted})")


def downgrade() -> None:
    pass
