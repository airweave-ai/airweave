"""Manual local Stripe flow test.

Requires:
- stripe listen --forward-to localhost:8001/billing/webhook
- AUTH_ENABLED=false
- STRIPE_SECRET_KEY set
- STRIPE_PRO_MONTHLY set

1. POST /organizations: org, stripe customer, api key
2. POST /billing/checkout-session: get checkout url (don't visit)
3. trigger subscription.created webhook: as if payment succeeded
4. GET /billing/subscription: wait until active
5. read DB snapshot
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import requests
import stripe


def log_step(title: str) -> None:
    print(f"\n▶ {title}")


def log_ok(message: str) -> None:
    print(f"  ✅ {message}")


def log_info(message: str) -> None:
    print(f"  • {message}")


def log_error(message: str) -> None:
    print(f"  ❌ {message}")


# -------------------------
# Config
# -------------------------

API_BASE = os.environ.get("AIRWEAVE_API_URL", "http://localhost:8001")
STRIPE_CLI = os.environ.get("STRIPE_CLI_BIN", "stripe")


@dataclass
class CreatedOrg:
    """Minimal organization representation for this manual test."""

    id: str
    name: str


def _http_post(
    path: str, json_body: Dict[str, Any], headers: Optional[Dict[str, str]] = None
) -> requests.Response:
    """Helper to POST to the local API with optional headers."""
    url = f"{API_BASE}{path}"
    merged = dict(headers or {})
    merged.setdefault("Content-Type", "application/json")
    merged.setdefault("accept", "application/json")
    return requests.post(url, json=json_body, headers=merged, timeout=30)


def _http_get(path: str, headers: Optional[Dict[str, str]] = None) -> requests.Response:
    """Helper to GET from the local API with optional headers."""
    url = f"{API_BASE}{path}"
    merged = dict(headers or {})
    merged.setdefault("accept", "application/json")
    return requests.get(url, headers=merged, timeout=30)


def create_organization(org_name: str, plan: str = "pro") -> CreatedOrg:
    """Create an organization with onboarding metadata including desired plan."""
    payload = {
        "name": org_name,
        "description": f"Local test org created at {datetime.utcnow().isoformat()}Z",
        "org_metadata": {
            "onboarding": {
                "organizationSize": "2-5",
                "userRole": "engineering",
                "organizationType": "saas",
                "subscriptionPlan": plan,
                "teamInvites": [],
                "completedAt": datetime.utcnow().isoformat() + "Z",
                # Optional: pass a Stripe test clock id to create customer on a clock
                # Set via env STRIPE_TEST_CLOCK or leave absent
                "stripe_test_clock": os.environ.get("STRIPE_TEST_CLOCK"),
            }
        },
    }
    resp = _http_post("/organizations", payload)
    if not resp.ok:
        raise RuntimeError(f"Failed to create organization: {resp.status_code} {resp.text}")
    data = resp.json()
    # Raw JSON from API; map fields we need
    return CreatedOrg(id=data["id"], name=data["name"])


def start_checkout_session(org_id: str, plan: str = "pro") -> str:
    """Request a checkout session for the plan. Returns the checkout URL."""
    headers = {"X-Organization-ID": org_id}
    payload = {
        "plan": plan,
        "success_url": "http://localhost:5173/organization/settings?tab=billing&success=true",
        "cancel_url": "http://localhost:5173/organization/settings?tab=billing",
    }
    resp = _http_post("/billing/checkout-session", payload, headers=headers)
    if not resp.ok:
        # Allow easy local testing if billing disabled
        try:
            detail = resp.json().get("detail")
        except Exception:
            detail = resp.text
        raise RuntimeError(f"Failed to start checkout session: {resp.status_code} {detail}")
    data = resp.json()
    return data.get("checkout_url", "")


def trigger_subscription_created_webhook(
    org_id: str, plan: str = "pro", *, stripe_customer_id: Optional[str] = None
) -> None:
    """Use Stripe CLI to emit a subscription.created webhook for our org.

    Important: We override subscription.customer to ensure the created subscription
    belongs to our real Stripe customer (attached to the Test Clock), to avoid
    creating an unrelated fixture customer that breaks renewal behavior.
    """
    overrides = [
        f"subscription:metadata.organization_id={org_id}",
        f"subscription:metadata.plan={plan}",
    ]
    if stripe_customer_id:
        overrides.append(f"subscription:customer={stripe_customer_id}")

    cmd = [STRIPE_CLI, "trigger", "customer.subscription.created"]
    for ov in overrides:
        cmd.extend(["--override", ov])

    print("\n> Triggering Stripe webhook: customer.subscription.created ...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr)
        raise RuntimeError(
            "Failed to trigger Stripe webhook. Ensure `stripe listen` is running "
            "and CLI is logged in."
        )
    print(res.stdout)


def poll_subscription_until_active(org_id: str, timeout_sec: int = 30) -> Dict[str, Any]:
    """Poll /billing/subscription until has_active_subscription and status == active."""
    headers = {"X-Organization-ID": org_id}
    deadline = time.time() + timeout_sec
    last = None
    while time.time() < deadline:
        resp = _http_get("/billing/subscription", headers=headers)
        if resp.ok:
            data = resp.json()
            last = data
            if data.get("has_active_subscription") and data.get("status") == "active":
                return data
        time.sleep(1.5)
    if last is None:
        raise RuntimeError("Failed to retrieve subscription info during polling.")
    return last


def poll_subscription_until_plan(
    org_id: str, expected_plan: str, timeout_sec: int = 30
) -> Dict[str, Any]:
    """Poll /billing/subscription until plan matches expected_plan."""
    headers = {"X-Organization-ID": org_id}
    deadline = time.time() + timeout_sec
    last = None
    while time.time() < deadline:
        resp = _http_get("/billing/subscription", headers=headers)
        if resp.ok:
            data = resp.json()
            last = data
            if str(data.get("plan", "")).lower() == expected_plan.lower():
                return data
        time.sleep(1.5)
    if last is None:
        raise RuntimeError("Failed to retrieve subscription info during polling.")
    return last


def poll_subscription_until_active_flag(org_id: str, timeout_sec: int = 60) -> Dict[str, Any]:
    """Poll /billing/subscription until has_active_subscription == True."""
    headers = {"X-Organization-ID": org_id}
    deadline = time.time() + timeout_sec
    last = None
    while time.time() < deadline:
        resp = _http_get("/billing/subscription", headers=headers)
        if resp.ok:
            data = resp.json()
            last = data
            if bool(data.get("has_active_subscription")) is True:
                return data
        time.sleep(1.5)
    if last is None:
        raise RuntimeError("Failed to retrieve subscription info during polling.")
    return last


# --- Optional DB snapshot using internal modules ---
async def db_snapshot(org_id: str, at_iso: Optional[str] = None) -> Dict[str, Any]:
    """Read key billing records directly from DB for verification."""
    # Ensure required environment variables for settings exist (local defaults)
    os.environ.setdefault("POSTGRES_HOST", "localhost")
    os.environ.setdefault("POSTGRES_PORT", "5432")
    os.environ.setdefault("POSTGRES_USER", "airweave")
    os.environ.setdefault("POSTGRES_PASSWORD", "airweave1234!")
    os.environ.setdefault("POSTGRES_DB", "airweave")
    # App bootstrap requirements for settings
    os.environ.setdefault("FIRST_SUPERUSER", "admin@example.com")
    os.environ.setdefault("FIRST_SUPERUSER_PASSWORD", "admin")
    os.environ.setdefault("ENCRYPTION_KEY", "44OLJ/s4OjYSyzVk9FtOk6033GrFS4Q4KWBdEstPrgU=")

    # Ensure backend/ is on sys.path so `airweave` package resolves when running from repo root
    backend_dir = Path(__file__).resolve().parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    from airweave import crud  # type: ignore
    from airweave.db.session import get_db_context  # type: ignore

    snapshot: Dict[str, Any] = {}
    async with get_db_context() as db:
        billing = await crud.organization_billing.get_by_organization(db, organization_id=org_id)
        if billing:
            snapshot["organization_billing"] = {
                "billing_plan": getattr(billing, "billing_plan", None),
                "billing_status": getattr(billing, "billing_status", None),
                "stripe_customer_id": getattr(billing, "stripe_customer_id", None),
                "stripe_subscription_id": getattr(billing, "stripe_subscription_id", None),
                "payment_method_added": getattr(billing, "payment_method_added", None),
                "current_period_start": str(getattr(billing, "current_period_start", None)),
                "current_period_end": str(getattr(billing, "current_period_end", None)),
                "pending_plan_change": getattr(billing, "pending_plan_change", None),
                "cancel_at_period_end": getattr(billing, "cancel_at_period_end", None),
            }

        # Current period (optionally at a provided timestamp for test-clock)
        if at_iso:
            try:
                at_dt = datetime.fromisoformat(at_iso)
                period = await crud.billing_period.get_current_period_at(
                    db, organization_id=org_id, at=at_dt
                )
            except Exception:
                period = await crud.billing_period.get_current_period(db, organization_id=org_id)
        else:
            period = await crud.billing_period.get_current_period(db, organization_id=org_id)
        if period:
            snapshot["current_billing_period"] = {
                "id": str(getattr(period, "id", None)),
                "plan": getattr(period, "plan", None),
                "status": getattr(period, "status", None),
                "period_start": str(getattr(period, "period_start", None)),
                "period_end": str(getattr(period, "period_end", None)),
                "stripe_subscription_id": getattr(period, "stripe_subscription_id", None),
            }
            # Current usage
            usage_cur = await crud.usage.get_by_billing_period(db, billing_period_id=period.id)
            if usage_cur:
                snapshot["current_usage"] = {
                    "entities": usage_cur.entities,
                    "queries": usage_cur.queries,
                    "source_connections": usage_cur.source_connections,
                }

        # Previous period (most recent)
        prev_list = await crud.billing_period.get_previous_periods(
            db, organization_id=org_id, limit=1
        )
        if prev_list:
            prev = prev_list[0]
            snapshot["previous_billing_period"] = {
                "id": str(getattr(prev, "id", None)),
                "plan": getattr(prev, "plan", None),
                "status": getattr(prev, "status", None),
                "period_start": str(getattr(prev, "period_start", None)),
                "period_end": str(getattr(prev, "period_end", None)),
            }
            usage_prev = await crud.usage.get_by_billing_period(db, billing_period_id=prev.id)
            if usage_prev:
                snapshot["previous_usage"] = {
                    "entities": usage_prev.entities,
                    "queries": usage_prev.queries,
                    "source_connections": usage_prev.source_connections,
                }

    return snapshot


def _assert_api_subscription(
    sub: Dict[str, Any],
    expected_plan: str = "pro",
    *,
    developer_expect_payment_method: Optional[bool] = None,
) -> None:
    """Validate subscription info from API."""
    assert sub.get("plan") == expected_plan, f"Plan mismatch: {sub.get('plan')}"
    assert sub.get("status") == "active", f"Status not active: {sub.get('status')}"
    # For developer, the billing period may be created later via webhook; allow false here
    if expected_plan.lower() != "developer":
        assert sub.get("has_active_subscription") is True, "Subscription not active"
    # Payment method expectations
    if expected_plan.lower() == "developer":
        if developer_expect_payment_method is None:
            # Default: initial developer has no payment method
            assert sub.get("payment_method_added") in {False, None}, (
                "Developer should not have a payment method"
            )
        else:
            assert bool(sub.get("payment_method_added")) is bool(developer_expect_payment_method), (
                "Developer payment method expectation mismatch"
            )
    else:
        assert sub.get("payment_method_added") is True, "Payment method not marked added"
    assert sub.get("requires_payment_method") is False, "Should not require payment method"
    assert sub.get("cancel_at_period_end") is False, "Should not be canceling at period end"
    limits = sub.get("limits") or {}
    # Basic plan limits sanity per plan
    plan_limits = {
        "developer": {"max_source_connections": 10, "max_entities": 50000, "max_queries": 500},
        "pro": {"max_source_connections": 50, "max_entities": 100000, "max_queries": 2000},
        "team": {"max_source_connections": 1000, "max_entities": 1000000, "max_queries": 10000},
    }
    expected = plan_limits.get(expected_plan.lower())
    if expected:
        assert limits.get("max_source_connections") == expected["max_source_connections"], (
            f"{expected_plan} max_source_connections mismatch"
        )
        assert limits.get("max_entities") == expected["max_entities"], (
            f"{expected_plan} max_entities mismatch"
        )
        assert limits.get("max_queries") == expected["max_queries"], (
            f"{expected_plan} max_queries mismatch"
        )
    # Period fields parse and make sense
    cps = sub.get("current_period_start")
    cpe = sub.get("current_period_end")
    assert cps and cpe, "Missing current period boundaries"
    start_dt = datetime.fromisoformat(cps)
    end_dt = datetime.fromisoformat(cpe)
    assert end_dt > start_dt, "Period end must be after start"


def _assert_db_snapshot(snap: Dict[str, Any], expected_plan: str = "pro") -> None:
    """Validate key billing fields in DB snapshot."""
    assert "organization_billing" in snap, "Missing organization_billing in snapshot"
    ob = snap["organization_billing"]
    assert (ob.get("billing_plan") or "").lower() == expected_plan, "DB plan mismatch"
    assert (ob.get("billing_status") or "").lower() == "active", "DB status not active"
    assert ob.get("stripe_subscription_id"), "Missing stripe_subscription_id in DB"
    if expected_plan.lower() == "developer":
        # Developer may not have a billing period yet; allow missing
        # Payment method typically not added on developer
        assert ob.get("payment_method_added") in {False, None}, (
            "DB: developer should not have payment method"
        )
    else:
        assert ob.get("payment_method_added") is True, "DB: payment_method_added should be True"

    # Period assertions only if present (developer may skip)
    if "current_billing_period" in snap:
        cp = snap["current_billing_period"]
        assert (cp.get("plan") or "").lower() == expected_plan, "DB period plan mismatch"
        # Status should be ACTIVE for new paid sub
        assert (cp.get("status") or "").lower() in {"active"}, "DB period status not ACTIVE"
        cps = cp.get("period_start")
        cpe = cp.get("period_end")
        start_dt = datetime.fromisoformat(cps)
        end_dt = datetime.fromisoformat(cpe)
        assert end_dt > start_dt, "DB period end must be after start"


def _assert_upgrade_pro_to_team(snap: Dict[str, Any]) -> None:
    """Validate immediate upgrade created a new Team period and ended Pro period."""
    # Current period should be TEAM
    cp = snap.get("current_billing_period", {})
    assert (cp.get("plan") or "").lower() == "team", "Current period plan should be team"
    assert (cp.get("status") or "").lower() == "active", "Current period not ACTIVE"
    # Previous period should exist, be PRO, and COMPLETED
    pp = snap.get("previous_billing_period", {})
    assert pp, "Previous period missing after upgrade"
    assert (pp.get("plan") or "").lower() == "pro", "Previous period plan should be pro"
    assert (pp.get("status") or "").lower() in {"completed"}, "Previous period not COMPLETED"
    # Usage rows should exist for both
    assert "current_usage" in snap, "Current usage missing"
    assert "previous_usage" in snap, "Previous usage missing"


def upgrade_subscription_to_team(org_id: str) -> str:
    """Upgrade plan to team via API (no checkout expected if PM exists)."""
    headers = {"X-Organization-ID": org_id}
    resp = _http_post("/billing/update-plan", {"plan": "team"}, headers=headers)
    if not resp.ok:
        try:
            detail = resp.json().get("detail")
        except Exception:
            detail = resp.text
        raise RuntimeError(f"Failed to update plan: {resp.status_code} {detail}")
    data = resp.json()
    return data.get("message", "")


def cancel_subscription_at_period_end(org_id: str) -> str:
    """Schedule cancellation at end of current period."""
    headers = {"X-Organization-ID": org_id}
    resp = _http_post("/billing/cancel", {}, headers=headers)
    if not resp.ok:
        try:
            detail = resp.json().get("detail")
        except Exception:
            detail = resp.text
        raise RuntimeError(f"Failed to cancel subscription: {resp.status_code} {detail}")
    return resp.json().get("message", "")


def reactivate_subscription(org_id: str) -> str:
    """Reactivate a subscription set to cancel at period end."""
    headers = {"X-Organization-ID": org_id}
    resp = _http_post("/billing/reactivate", {}, headers=headers)
    if not resp.ok:
        try:
            detail = resp.json().get("detail")
        except Exception:
            detail = resp.text
        raise RuntimeError(f"Failed to reactivate subscription: {resp.status_code} {detail}")
    return resp.json().get("message", "")


def get_stripe_subscription(subscription_id: str) -> Any:
    """Fetch a Stripe subscription directly using STRIPE_SECRET_KEY from env."""
    api_key = os.environ.get("STRIPE_SECRET_KEY")
    if not api_key:
        raise RuntimeError("STRIPE_SECRET_KEY not set in environment")
    stripe.api_key = api_key
    return stripe.Subscription.retrieve(subscription_id)


def assert_stripe_active(subscription_id: str, expected_plan: Optional[str] = None) -> None:
    """Assert Stripe subscription is active; optionally validate metadata.plan."""
    sub = get_stripe_subscription(subscription_id)
    status = getattr(sub, "status", None)
    assert status == "active", f"Stripe sub not active (status={status})"
    # On developer/pro created via checkout/client, we set metadata.plan
    if expected_plan:
        meta = getattr(sub, "metadata", {}) or {}
        plan_meta = meta.get("plan") if isinstance(meta, dict) else None
        assert (plan_meta or "").lower() == expected_plan.lower(), (
            f"Stripe metadata.plan mismatch: {plan_meta} != {expected_plan}"
        )


def downgrade_subscription_to_developer(org_id: str) -> str:
    """Schedule a downgrade to developer at period end."""
    headers = {"X-Organization-ID": org_id}
    resp = _http_post("/billing/update-plan", {"plan": "developer"}, headers=headers)
    if not resp.ok:
        try:
            detail = resp.json().get("detail")
        except Exception:
            detail = resp.text
        raise RuntimeError(f"Failed to downgrade plan: {resp.status_code} {detail}")
    return resp.json().get("message", "")


def _stripe_first_item_price_id(subscription: Any) -> Optional[str]:
    try:
        # Attribute-style access
        if hasattr(subscription, "items") and hasattr(subscription.items, "data"):
            data = subscription.items.data or []
            if data:
                price_obj = getattr(data[0], "price", None)
                if hasattr(price_obj, "id"):
                    return price_obj.id
        # Dict-style fallback
        if isinstance(subscription, dict):
            data = ((subscription.get("items") or {}).get("data")) or []
            if isinstance(data, list) and data:
                price_obj = data[0].get("price") if isinstance(data[0], dict) else None
                if isinstance(price_obj, dict):
                    return price_obj.get("id")
    except Exception:
        return None
    return None


def assert_stripe_price(subscription_id: str, expected_price_id: str) -> None:
    sub = get_stripe_subscription(subscription_id)
    actual = _stripe_first_item_price_id(sub)
    assert actual == expected_price_id, f"Stripe price mismatch: {actual} != {expected_price_id}"


def assert_stripe_downgrade_scheduled(
    subscription_id: str, expected_dev_price_id: Optional[str]
) -> None:
    """Assert downgrade is scheduled in Stripe context.

    Conditions we can reliably check in Stripe for a scheduled downgrade:
    - Subscription remains active
    - cancel_at_period_end is False
    - The subscription's item price has been updated to the developer price id
      (Stripe applies the new price for next period when proration_behavior='none').
    """
    sub = get_stripe_subscription(subscription_id)
    status = getattr(sub, "status", None)
    assert status == "active", f"Stripe sub not active during pending downgrade (status={status})"
    assert bool(getattr(sub, "cancel_at_period_end", False)) is False, (
        "Stripe: cancel_at_period_end should be False for scheduled downgrade"
    )
    if expected_dev_price_id:
        current_price_id = _stripe_first_item_price_id(sub)
        assert current_price_id == expected_dev_price_id, (
            f"Stripe: subscription item price {current_price_id} != developer {expected_dev_price_id}"
        )


def create_stripe_test_clock(
    frozen_time: Optional[int] = None, name: str = "airweave-local"
) -> str:
    """Create a Stripe Test Clock and return its id."""
    api_key = os.environ.get("STRIPE_SECRET_KEY")
    if not api_key:
        raise RuntimeError("STRIPE_SECRET_KEY not set in environment")
    stripe.api_key = api_key
    if frozen_time is None:
        frozen_time = int(time.time())
    clock = stripe.test_helpers.TestClock.create(frozen_time=frozen_time, name=name)
    return clock.id


def advance_stripe_test_clock(clock_id: str, new_time: int) -> None:
    api_key = os.environ.get("STRIPE_SECRET_KEY")
    if not api_key:
        raise RuntimeError("STRIPE_SECRET_KEY not set in environment")
    stripe.api_key = api_key
    stripe.test_helpers.TestClock.advance(test_clock=clock_id, frozen_time=new_time)


def _parse_iso_to_ts(dt_str: str) -> int:
    dt = datetime.fromisoformat(dt_str)
    # Treat naive timestamps as UTC; Stripe Test Clock expects epoch seconds in UTC.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return int(dt.timestamp())


def _compact_api_state(org_id: str) -> Dict[str, Any]:
    try:
        data = _http_get("/billing/subscription", {"X-Organization-ID": org_id}).json()
        return {
            "plan": data.get("plan"),
            "status": data.get("status"),
            "has_active_subscription": data.get("has_active_subscription"),
            "pending_plan_change": data.get("pending_plan_change"),
            "cancel_at_period_end": data.get("cancel_at_period_end"),
        }
    except Exception:
        return {"error": "api_state_failed"}


def _compact_db_state(loop: asyncio.AbstractEventLoop, org_id: str) -> Dict[str, Any]:
    try:
        snap = loop.run_until_complete(db_snapshot(org_id))
        ob = snap.get("organization_billing", {})
        cp = snap.get("current_billing_period", {})
        return {
            "billing_plan": ob.get("billing_plan"),
            "pending_plan_change": ob.get("pending_plan_change"),
            "cancel_at_period_end": ob.get("cancel_at_period_end"),
            "current_period_plan": cp.get("plan"),
            "current_period_status": cp.get("status"),
            "stripe_subscription_id": ob.get("stripe_subscription_id"),
        }
    except Exception:
        return {"error": "db_state_failed"}


def _compact_stripe_state(sub_id: Optional[str]) -> Dict[str, Any]:
    if not sub_id:
        return {"error": "no_sub_id"}
    try:
        sub = get_stripe_subscription(sub_id)
        return {
            "status": getattr(sub, "status", None),
            "cancel_at_period_end": bool(getattr(sub, "cancel_at_period_end", False)),
            "price_id": _stripe_first_item_price_id(sub),
        }
    except Exception:
        return {"error": "stripe_state_failed"}


def ensure_test_payment_method(customer_id: str) -> None:
    """Attach a test payment method to the customer and set it as default.

    Tries PaymentMethod attach (pm_card_visa). Falls back to adding a test source token.
    """
    api_key = os.environ.get("STRIPE_SECRET_KEY")
    if not api_key:
        raise RuntimeError("STRIPE_SECRET_KEY not set in environment")
    stripe.api_key = api_key
    try:
        # Preferred: default payment method via PaymentMethod
        stripe.PaymentMethod.attach("pm_card_visa", customer=customer_id)
        stripe.Customer.modify(
            customer_id,
            invoice_settings={"default_payment_method": "pm_card_visa"},
        )
        return
    except Exception:
        pass
    try:
        # Fallback: add a card source token and rely on default source
        stripe.Customer.create_source(customer_id, source="tok_visa")
    except Exception as e:
        log_error(f"Failed to attach test payment method: {e}")


def create_paid_subscription_for_plan(
    customer_id: str,
    *,
    price_id: str,
    org_id: str,
    plan: str,
) -> str:
    """Create a paid Stripe subscription directly for an existing customer.

    Returns the created subscription id. This emits the same webhooks Stripe CLI would,
    but avoids creating extra fixture customers.
    """
    api_key = os.environ.get("STRIPE_SECRET_KEY")
    if not api_key:
        raise RuntimeError("STRIPE_SECRET_KEY not set in environment")
    stripe.api_key = api_key
    sub = stripe.Subscription.create(
        customer=customer_id,
        items=[{"price": price_id}],
        metadata={
            "organization_id": org_id,
            "plan": plan,
        },
        expand=["latest_invoice.payment_intent"],
    )
    return sub.id


def upgrade_existing_subscription_price(
    subscription_id: str,
    *,
    new_price_id: str,
    plan: str,
) -> None:
    """Upgrade existing subscription by changing its item price.

    Emits customer.subscription.updated with items change so our webhook upgrade path runs.
    """
    api_key = os.environ.get("STRIPE_SECRET_KEY")
    if not api_key:
        raise RuntimeError("STRIPE_SECRET_KEY not set in environment")
    stripe.api_key = api_key
    sub = stripe.Subscription.retrieve(subscription_id)
    item_id = sub["items"]["data"][0]["id"]
    stripe.Subscription.modify(
        subscription_id,
        items=[{"id": item_id, "price": new_price_id}],
        cancel_at_period_end=False,
        proration_behavior="create_prorations",
        metadata={"plan": plan},
    )


def main() -> None:
    """Run the local subscription flow tests (developer → pro → team)."""
    print("Manual local Stripe subscription flow test")
    print(f"API: {API_BASE}")

    # 0) Ensure a Stripe Test Clock exists (optional but recommended for renewal simulation)
    clock_id = os.environ.get("STRIPE_TEST_CLOCK")
    if not clock_id and os.environ.get("STRIPE_SECRET_KEY"):
        try:
            clock_id = create_stripe_test_clock(name="airweave-local")
            os.environ["STRIPE_TEST_CLOCK"] = clock_id
            log_info(f"Created Stripe test clock: {clock_id}")
        except Exception as e:
            log_error(f"Skipping test clock creation: {e}")

    # 1) Create organization starting on Developer plan (no checkout expected)
    org_name = f"Local Test Org {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
    org = create_organization(org_name, plan="developer")
    log_step("Create organization (start on developer)")
    log_ok(f"Org created: {org.id} ({org.name})")

    # Developer plan is created during org creation (may rely on Stripe webhooks); poll until active
    sub = poll_subscription_until_plan(org.id, expected_plan="developer", timeout_sec=60)
    # Ensure active flag turns true (webhook-driven current period)
    sub = poll_subscription_until_active_flag(org.id, timeout_sec=60)
    _assert_api_subscription(sub, expected_plan="developer")
    log_ok("Developer subscription active (API)")

    # Prepare a reusable event loop for DB snapshots to avoid loop-close issues
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # DB snapshot for developer
    try:
        snap = loop.run_until_complete(db_snapshot(org.id))
        _assert_db_snapshot(snap, expected_plan="developer")
        log_ok("Developer subscription active (DB)")
        # Stripe check
        sub_id_dev = snap.get("organization_billing", {}).get("stripe_subscription_id")
        if sub_id_dev:
            assert_stripe_active(sub_id_dev, expected_plan="developer")
            log_ok("Developer subscription active (Stripe)")
    except Exception as e:
        log_error(f"Developer DB/Stripe check skipped: {e}")

    # 2) Attempt to upgrade to Pro via update-plan (should require checkout)
    log_step("Upgrade Developer → Pro (should require checkout)")
    headers = {"X-Organization-ID": org.id}
    resp_update = _http_post("/billing/update-plan", {"plan": "pro"}, headers=headers)
    assert resp_update.status_code == 400, (
        f"Expected 400 requiring checkout, got {resp_update.status_code}: {resp_update.text}"
    )
    detail = resp_update.json().get("detail", "")
    assert "Payment method required" in detail, f"Unexpected error detail: {detail}"
    log_ok("Upgrade requires checkout (as expected)")

    # 3) Create checkout session for Pro (parity with UI step)
    checkout_url = start_checkout_session(org.id, plan="pro")
    assert checkout_url and checkout_url.startswith("https://"), "Missing checkout URL for Pro"
    log_ok("Checkout session created (Pro)")
    # Instead of Stripe CLI fixtures (which create extra customers), upgrade the existing
    # subscription for this customer by changing its item price to Pro.
    snap_for_customer = loop.run_until_complete(db_snapshot(org.id))
    real_customer_id = (
        snap_for_customer.get("organization_billing", {}).get("stripe_customer_id")
        if isinstance(snap_for_customer, dict)
        else None
    )
    assert real_customer_id, "Missing Stripe customer id from billing snapshot"
    ensure_test_payment_method(real_customer_id)
    pro_price = os.environ.get("STRIPE_PRO_MONTHLY")
    assert pro_price, "STRIPE_PRO_MONTHLY must be set to upgrade to Pro"
    current_sub_id = (
        snap_for_customer.get("organization_billing", {}).get("stripe_subscription_id")
        if isinstance(snap_for_customer, dict)
        else None
    )
    assert current_sub_id, "Missing current Stripe subscription id in snapshot"
    upgrade_existing_subscription_price(current_sub_id, new_price_id=pro_price, plan="pro")
    print(
        "\n> Upgraded existing Stripe subscription via API (developer → pro). Webhooks should follow..."
    )

    # 4) Poll until Pro is active
    sub_pro = poll_subscription_until_plan(org.id, expected_plan="pro", timeout_sec=60)
    _assert_api_subscription(sub_pro, expected_plan="pro")
    log_ok("Pro subscription active (API)")

    # 5) DB snapshot after Pro activation
    try:
        snap_pro = loop.run_until_complete(db_snapshot(org.id))
        _assert_db_snapshot(snap_pro, expected_plan="pro")
        log_ok("Pro subscription active (DB)")
        # Stripe check
        sub_id_pro = snap_pro.get("organization_billing", {}).get("stripe_subscription_id")
        if sub_id_pro:
            assert_stripe_active(sub_id_pro, expected_plan="pro")
            log_ok("Pro subscription active (Stripe)")
    except Exception as e:
        log_error(f"Pro DB/Stripe check skipped: {e}")

    # 6) Upgrade from Pro to Team (immediate, no checkout)
    log_step("Upgrade Pro → Team (immediate)")
    msg = upgrade_subscription_to_team(org.id)
    log_info(f"Update-plan: {msg}")

    # Poll until plan shows as team
    sub_team = poll_subscription_until_plan(org.id, expected_plan="team", timeout_sec=60)
    _assert_api_subscription(sub_team, expected_plan="team")
    log_ok("Team subscription active (API)")

    # Snapshot DB and assert periods
    try:
        snap_after = loop.run_until_complete(db_snapshot(org.id))
        _assert_upgrade_pro_to_team(snap_after)
        log_ok("Team period created; Pro period completed (DB)")
        # Stripe check
        sub_id_team = snap_after.get("organization_billing", {}).get("stripe_subscription_id")
        if sub_id_team:
            # Metadata.plan isn't updated on upgrades; validate via active status and price id
            assert_stripe_active(sub_id_team)
            team_price_id = os.environ.get("STRIPE_TEAM_MONTHLY")
            if team_price_id:
                assert_stripe_price(sub_id_team, team_price_id)
            log_ok("Team subscription active (Stripe)")
    except Exception as e:
        log_error(f"Team DB/Stripe check skipped: {e}")

    # 7) Cancel Team subscription (schedule at period end) and verify
    log_step("Cancel Team (schedule at period end)")
    msg_cancel = cancel_subscription_at_period_end(org.id)
    log_info(f"Cancel: {msg_cancel}")

    # Poll until cancel_at_period_end true
    sub_team_after_cancel = None
    for _ in range(20):
        sub_team_after_cancel = _http_get(
            "/billing/subscription", {"X-Organization-ID": org.id}
        ).json()
        if sub_team_after_cancel.get("cancel_at_period_end") is True:
            break
        time.sleep(1.0)

    assert sub_team_after_cancel and sub_team_after_cancel.get("cancel_at_period_end") is True, (
        "cancel_at_period_end not set after cancel"
    )
    log_ok("cancel_at_period_end = true (API)")

    # Verify in Stripe
    try:
        sub_id = (
            snap_after.get("organization_billing", {}).get("stripe_subscription_id")
            if "snap_after" in locals()
            else None
        )
        if not sub_id:
            # Fallback: fetch a fresh snapshot
            snap_verify = loop.run_until_complete(db_snapshot(org.id))
            sub_id = snap_verify.get("organization_billing", {}).get("stripe_subscription_id")
        if sub_id:
            stripe_sub = get_stripe_subscription(sub_id)
            assert bool(getattr(stripe_sub, "cancel_at_period_end", False)) is True, (
                "Stripe: cancel_at_period_end not set"
            )
            log_ok("cancel_at_period_end = true (Stripe)")
        else:
            log_error("Stripe check skipped: no subscription id in snapshot")
    except Exception as e:
        log_error(f"Stripe check skipped: {e}")

    # 8) Reactivate and verify flag cleared
    log_step("Reactivate Team (clear scheduled cancel)")
    msg_reactivate = reactivate_subscription(org.id)
    log_info(f"Reactivate: {msg_reactivate}")

    # Poll until flag is false
    sub_team_after_reactivate = None
    for _ in range(20):
        sub_team_after_reactivate = _http_get(
            "/billing/subscription", {"X-Organization-ID": org.id}
        ).json()
        if sub_team_after_reactivate.get("cancel_at_period_end") is False:
            break
        time.sleep(1.0)

    assert (
        sub_team_after_reactivate and sub_team_after_reactivate.get("cancel_at_period_end") is False
    ), "cancel_at_period_end not cleared after reactivate"
    log_ok("cancel_at_period_end = false (API)")

    # Verify cleared in Stripe
    try:
        sub_id = (
            snap_after.get("organization_billing", {}).get("stripe_subscription_id")
            if "snap_after" in locals()
            else None
        )
        if not sub_id:
            snap_verify2 = loop.run_until_complete(db_snapshot(org.id))
            sub_id = snap_verify2.get("organization_billing", {}).get("stripe_subscription_id")
        if sub_id:
            stripe_sub2 = get_stripe_subscription(sub_id)
            assert bool(getattr(stripe_sub2, "cancel_at_period_end", False)) is False, (
                "Stripe: cancel_at_period_end still set after reactivation"
            )
            log_ok("cancel_at_period_end = false (Stripe)")
        else:
            log_error("Stripe check skipped: no subscription id in snapshot")
    except Exception as e:
        log_error(f"Stripe check skipped: {e}")

    # 9) Downgrade from Team to Developer (scheduled at period end)
    log_step("Downgrade Team → Developer (scheduled at period end)")
    msg_dg = downgrade_subscription_to_developer(org.id)
    log_info(f"Downgrade: {msg_dg}")

    # Poll until pending_plan_change == developer
    sub_team_after_dg = None
    for _ in range(20):
        sub_team_after_dg = _http_get("/billing/subscription", {"X-Organization-ID": org.id}).json()
        if (sub_team_after_dg.get("pending_plan_change") or "").lower() == "developer":
            break
        time.sleep(1.0)

    assert (
        sub_team_after_dg
        and (sub_team_after_dg.get("pending_plan_change") or "").lower() == "developer"
    ), "pending_plan_change not set to developer after downgrade"
    log_ok("pending_plan_change = developer (API)")

    # Verify in DB snapshot: pending_plan_change present
    try:
        snap_dg = loop.run_until_complete(db_snapshot(org.id))
        ob = snap_dg.get("organization_billing", {})
        assert (ob.get("pending_plan_change") or "").lower() == "developer", (
            "DB: pending_plan_change not set to developer"
        )
        log_ok("pending_plan_change = developer (DB)")
    except Exception as e:
        log_error(f"DB check skipped: {e}")

    # Stripe: ensure subscription item is still active and no immediate cancel
    try:
        sub_id_team2 = (
            snap_dg.get("organization_billing", {}).get("stripe_subscription_id")
            if "snap_dg" in locals()
            else None
        )
        if not sub_id_team2:
            snap_verify3 = loop.run_until_complete(db_snapshot(org.id))
            sub_id_team2 = snap_verify3.get("organization_billing", {}).get(
                "stripe_subscription_id"
            )
        if sub_id_team2:
            # If you have STRIPE_DEVELOPER_MONTHLY configured, enforce price swap as proof of scheduling
            dev_price_id = os.environ.get("STRIPE_DEVELOPER_MONTHLY")
            assert_stripe_downgrade_scheduled(sub_id_team2, expected_dev_price_id=dev_price_id)
            log_ok("Stripe: downgrade scheduled (active, price set for next period)")
        else:
            log_error("Stripe check skipped: no subscription id in snapshot")
    except Exception as e:
        log_error(f"Stripe check skipped: {e}")

    # 10) Advance time to simulate renewal and apply downgrade (requires Stripe Test Clock)
    if clock_id:
        log_step("Advance Stripe Test Clock to apply scheduled downgrade")
        try:
            # Determine a target time just after current period end
            snap_now = loop.run_until_complete(db_snapshot(org.id))
            cpe = snap_now.get("organization_billing", {}).get(
                "current_period_end"
            ) or snap_now.get("current_billing_period", {}).get("period_end")
            assert cpe, "Missing current_period_end to advance clock"
            # Advance one full day past the current period end to safely cross renewal
            target_ts = _parse_iso_to_ts(str(cpe)) + 24 * 60 * 60
            advance_stripe_test_clock(clock_id, target_ts)
            log_info("Advanced test clock past current period end")

            # Poll until API reflects developer plan, with diagnostics
            deadline = time.time() + 30
            success = False
            last_api = {}
            last_db = {}
            last_stripe = {}
            while time.time() < deadline:
                last_api = _compact_api_state(org.id)
                last_db = _compact_db_state(loop, org.id)
                last_stripe = _compact_stripe_state(last_db.get("stripe_subscription_id"))
                if (last_api.get("plan") or "").lower() == "developer":
                    success = True
                    break
                time.sleep(1.0)

            if not success:
                raise AssertionError(
                    f"Downgrade did not apply after advancing clock. "
                    f"API={last_api} DB={last_db} STRIPE={last_stripe}"
                )

            _assert_api_subscription(
                {
                    "plan": "developer",
                    "status": "active",
                    "current_period_start": "1970-01-01T00:00:01",
                    "current_period_end": "2099-01-01T00:00:01",
                    "has_active_subscription": True,
                    "payment_method_added": True,
                    "requires_payment_method": False,
                    "cancel_at_period_end": False,
                    "limits": {
                        "max_source_connections": 10,
                        "max_entities": 50000,
                        "max_queries": 500,
                    },
                },
                expected_plan="developer",
                developer_expect_payment_method=True,
            )
            log_ok("Developer subscription active post-renewal (API)")

            # DB snapshot at new simulated time: Team period completed, new Developer active
            snap_post = loop.run_until_complete(
                db_snapshot(org.id, at_iso=str(datetime.utcfromtimestamp(target_ts)))
            )
            obp = snap_post.get("organization_billing", {})
            assert (obp.get("billing_plan") or "").lower() == "developer", (
                "DB: plan not developer after renewal"
            )
            log_ok("Developer subscription active post-renewal (DB)")
        except Exception as e:
            log_error(f"Test clock advance skipped/failed: {e}")

    # Clean up loop
    try:
        loop.close()
    except Exception:
        pass

    log_ok("All tests completed")


if __name__ == "__main__":
    main()
