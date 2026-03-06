"""Cleanup stale billing data: downgrade freeloaders, complete expired periods.

Revision ID: e3f4g5h6i7j8
Revises: d2e3f4g5h6i7
Create Date: 2026-03-05 22:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "e3f4g5h6i7j8"
down_revision = "d2e3f4g5h6i7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Clean up stale billing data produced by the Feb 26–Mar 4 webhook outage."""
    conn = op.get_bind()

    # 1. Downgrade orgs that selected a paid plan but never completed checkout.
    #    They have billing_plan = pro/team, no stripe_subscription_id, and
    #    zero billing periods.
    result = conn.execute(
        sa.text("""
            UPDATE organization_billing
            SET billing_plan = 'developer',
                modified_at = NOW()
            WHERE billing_plan IN ('pro', 'team')
              AND stripe_subscription_id IS NULL
              AND organization_id::uuid NOT IN (
                  SELECT DISTINCT organization_id FROM billing_period
              )
        """)
    )
    print(f"  -> Downgraded {result.rowcount} unpaid pro/team orgs to developer")

    # 2. Complete billing periods whose end date is in the past but are still
    #    marked as 'active' (orphaned from missed renewal webhooks).
    result = conn.execute(
        sa.text("""
            UPDATE billing_period
            SET status = 'completed',
                modified_at = NOW()
            WHERE status = 'active'
              AND period_end < NOW()
        """)
    )
    print(f"  -> Completed {result.rowcount} expired billing periods")

    # 3. For orgs with multiple overlapping active periods, keep the latest
    #    and complete the rest.
    result = conn.execute(
        sa.text("""
            UPDATE billing_period
            SET status = 'completed', modified_at = NOW()
            WHERE status = 'active'
              AND id NOT IN (
                SELECT DISTINCT ON (organization_id) id
                FROM billing_period
                WHERE status = 'active'
                ORDER BY organization_id, period_start DESC
              )
              AND organization_id IN (
                SELECT organization_id
                FROM billing_period
                WHERE status = 'active'
                GROUP BY organization_id
                HAVING COUNT(*) > 1
              )
        """)
    )
    print(f"  -> Completed {result.rowcount} duplicate active periods")


def downgrade() -> None:
    """No automated downgrade — data migration only."""
    pass
