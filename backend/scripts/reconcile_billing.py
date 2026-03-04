#!/usr/bin/env python3
"""Reconcile billing state after webhook outage.

This script:
1. Lists failed webhook deliveries from Stripe for the outage window
2. Groups events by customer/subscription
3. For each subscription, fetches the current Stripe state
4. Reconciles our DB: fixes orphaned periods, fills gaps, updates billing records

Usage:
    # Dry-run (default) — shows what would change, writes nothing
    python -m scripts.reconcile_billing --since 2026-02-26 --until 2026-03-04

    # Apply changes
    python -m scripts.reconcile_billing --since 2026-02-26 --until 2026-03-04 --apply

Prerequisites:
    pip install stripe
    export STRIPE_SECRET_KEY=sk_live_...

    Or configure via .env / settings.
"""

import argparse
import asyncio
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

import stripe
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.config import settings
from airweave.db.session import AsyncSessionLocal
from airweave.models.billing_period import BillingPeriod
from airweave.models.organization_billing import OrganizationBilling
from airweave.schemas.billing_period import BillingPeriodStatus


async def get_billing_by_customer(db: AsyncSession, customer_id: str) -> OrganizationBilling | None:
    """Look up billing record by Stripe customer ID."""
    result = await db.execute(
        select(OrganizationBilling).where(OrganizationBilling.stripe_customer_id == customer_id)
    )
    return result.scalar_one_or_none()


async def get_billing_by_subscription(
    db: AsyncSession, subscription_id: str
) -> OrganizationBilling | None:
    """Look up billing record by Stripe subscription ID."""
    result = await db.execute(
        select(OrganizationBilling).where(
            OrganizationBilling.stripe_subscription_id == subscription_id
        )
    )
    return result.scalar_one_or_none()


async def get_periods_for_org(db: AsyncSession, organization_id: UUID) -> list[BillingPeriod]:
    """Get all billing periods for an org, ordered by start date."""
    result = await db.execute(
        select(BillingPeriod)
        .where(BillingPeriod.organization_id == organization_id)
        .order_by(BillingPeriod.period_start)
    )
    return list(result.scalars().all())


async def get_active_periods_for_org(
    db: AsyncSession, organization_id: UUID
) -> list[BillingPeriod]:
    """Get all ACTIVE/GRACE billing periods for an org."""
    result = await db.execute(
        select(BillingPeriod)
        .where(
            and_(
                BillingPeriod.organization_id == organization_id,
                BillingPeriod.status.in_(
                    [
                        BillingPeriodStatus.ACTIVE,
                        BillingPeriodStatus.GRACE,
                    ]
                ),
            )
        )
        .order_by(BillingPeriod.period_start)
    )
    return list(result.scalars().all())


def list_failed_events(since: datetime, until: datetime) -> list[dict]:
    """Use Stripe CLI to list failed webhook events in the window."""
    since_ts = int(since.timestamp())
    until_ts = int(until.timestamp())

    print(f"Fetching failed events from {since.isoformat()} to {until.isoformat()}...")

    all_events = []
    starting_after = None

    while True:
        cmd = [
            "stripe",
            "events",
            "list",
            "--limit",
            "100",
            f"--created[gte]={since_ts}",
            f"--created[lte]={until_ts}",
        ]
        if starting_after:
            cmd.extend(["--starting-after", starting_after])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Stripe CLI error: {result.stderr}", file=sys.stderr)
            break

        data = json.loads(result.stdout)
        events = data.get("data", [])
        if not events:
            break

        all_events.extend(events)
        starting_after = events[-1]["id"]

        if not data.get("has_more", False):
            break

    print(f"Found {len(all_events)} total events in window")
    return all_events


def group_events_by_subscription(events: list[dict]) -> dict[str, list[dict]]:
    """Group events by subscription ID for ordered processing."""
    groups: dict[str, list[dict]] = defaultdict(list)

    for event in events:
        obj = event.get("data", {}).get("object", {})
        sub_id = None

        if event["type"].startswith("customer.subscription"):
            sub_id = obj.get("id")
        elif "subscription" in obj:
            sub_id = obj["subscription"]
        elif "customer" in obj:
            sub_id = f"customer:{obj['customer']}"

        if sub_id:
            groups[sub_id].append(event)

    for sub_id in groups:
        groups[sub_id].sort(key=lambda e: e["created"])

    return dict(groups)


async def reconcile_subscription(  # noqa: C901
    db: AsyncSession,
    subscription_id: str,
    events: list[dict],
    apply: bool,
) -> dict:
    """Reconcile a single subscription's billing state."""
    report = {
        "subscription_id": subscription_id,
        "event_count": len(events),
        "event_types": [e["type"] for e in events],
        "actions": [],
    }

    if subscription_id.startswith("customer:"):
        customer_id = subscription_id.split(":", 1)[1]
        billing = await get_billing_by_customer(db, customer_id)
    else:
        billing = await get_billing_by_subscription(db, subscription_id)

    if not billing:
        report["actions"].append("SKIP: no billing record found in DB")
        return report

    org_id = billing.organization_id
    report["organization_id"] = str(org_id)
    report["current_plan"] = billing.billing_plan
    report["current_status"] = billing.billing_status

    # Fetch current subscription state from Stripe
    try:
        if not subscription_id.startswith("customer:"):
            sub = stripe.Subscription.retrieve(subscription_id)
        else:
            report["actions"].append("SKIP: customer-only events (no subscription)")
            return report
    except stripe.error.InvalidRequestError:
        report["actions"].append("SKIP: subscription not found in Stripe (deleted?)")
        return report

    stripe_period_start = datetime.utcfromtimestamp(sub.current_period_start)
    stripe_period_end = datetime.utcfromtimestamp(sub.current_period_end)

    # Check for stale billing record dates
    if billing.current_period_start and billing.current_period_start < stripe_period_start:
        report["actions"].append(
            f"UPDATE billing record: period_start "
            f"{billing.current_period_start} → {stripe_period_start}"
        )
        if apply:
            billing.current_period_start = stripe_period_start
            billing.current_period_end = stripe_period_end

    # Check billing status matches Stripe
    if billing.billing_status != sub.status:
        report["actions"].append(f"UPDATE billing status: {billing.billing_status} → {sub.status}")
        if apply:
            billing.billing_status = sub.status

    # Find period issues
    active_periods = await get_active_periods_for_org(db, org_id)

    if len(active_periods) > 1:
        report["actions"].append(
            f"FIX: {len(active_periods)} overlapping active periods — "
            f"keeping latest, completing others"
        )
        if apply:
            latest = active_periods[-1]
            for period in active_periods[:-1]:
                period.status = BillingPeriodStatus.COMPLETED
                if period.period_end > latest.period_start:
                    period.period_end = latest.period_start

    # Check if current Stripe period has a matching billing period
    has_current_period = False
    for period in active_periods:
        if (
            abs((period.period_start - stripe_period_start).total_seconds()) < 86400
            and abs((period.period_end - stripe_period_end).total_seconds()) < 86400
        ):
            has_current_period = True
            break

    if not has_current_period and active_periods:
        latest = active_periods[-1]
        if latest.period_end <= stripe_period_start:
            report["actions"].append(
                f"GAP: latest period ends {latest.period_end}, "
                f"Stripe period starts {stripe_period_start} — renewal period missing"
            )
    elif not has_current_period and not active_periods:
        report["actions"].append(
            f"MISSING: no active period at all, Stripe shows "
            f"{stripe_period_start} → {stripe_period_end}"
        )

    if not report["actions"]:
        report["actions"].append("OK: billing state consistent with Stripe")

    if apply:
        await db.commit()

    return report


async def main(since: datetime, until: datetime, apply: bool) -> None:
    """Run reconciliation across all affected subscriptions."""
    stripe.api_key = settings.STRIPE_SECRET_KEY

    events = list_failed_events(since, until)
    groups = group_events_by_subscription(events)

    print(f"\n{'=' * 60}")
    print(f"Subscriptions affected: {len(groups)}")
    print(f"Mode: {'APPLY' if apply else 'DRY-RUN'}")
    print(f"{'=' * 60}\n")

    async with AsyncSessionLocal() as db:
        for sub_id, sub_events in groups.items():
            report = await reconcile_subscription(db, sub_id, sub_events, apply)

            print(f"\n--- {report['subscription_id']} ---")
            print(f"  Org: {report.get('organization_id', 'N/A')}")
            print(f"  Plan: {report.get('current_plan', 'N/A')}")
            print(f"  Events: {report['event_count']} ({', '.join(report['event_types'])})")
            for action in report["actions"]:
                print(f"  → {action}")

    print(f"\n{'=' * 60}")
    if not apply:
        print("DRY-RUN complete. Re-run with --apply to make changes.")
    else:
        print("APPLY complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reconcile billing after webhook outage")
    parser.add_argument(
        "--since",
        required=True,
        type=str,
        help="Start of outage window (ISO date, e.g. 2026-02-26)",
    )
    parser.add_argument(
        "--until",
        required=True,
        type=str,
        help="End of outage window (ISO date, e.g. 2026-03-04)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Apply changes (default is dry-run)",
    )
    args = parser.parse_args()

    since_dt = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
    until_dt = datetime.fromisoformat(args.until).replace(tzinfo=timezone.utc)

    asyncio.run(main(since_dt, until_dt, args.apply))
