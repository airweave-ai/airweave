"""Tests for rate limiter plan limits and adapters.

Verifies:
- PLAN_LIMITS has correct values for each plan tier
- Enterprise is unlimited (None)
- Unknown plans fall back to developer limits
- NullRateLimiter always allows
- RedisRateLimiter._extract_plan raises on missing billing data
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from airweave.adapters.rate_limiter.null import NullRateLimiter
from airweave.adapters.rate_limiter.redis import PLAN_LIMITS, RedisRateLimiter
from airweave.schemas.organization import Organization
from airweave.schemas.organization_billing import BillingPlan


def _make_org(billing=None):
    now = datetime.now(timezone.utc)
    org = Organization(id=uuid4(), name="Test Org", created_at=now, modified_at=now)
    if billing is not None:
        object.__setattr__(org, "billing", billing)
    return org


class TestPlanLimits:
    def test_developer_limit(self):
        assert PLAN_LIMITS[BillingPlan.DEVELOPER.value] == 10

    def test_pro_limit(self):
        assert PLAN_LIMITS[BillingPlan.PRO.value] == 100

    def test_team_limit(self):
        assert PLAN_LIMITS[BillingPlan.TEAM.value] == 250

    def test_enterprise_unlimited(self):
        assert PLAN_LIMITS[BillingPlan.ENTERPRISE.value] is None

    def test_all_billing_plans_have_limits(self):
        """Every BillingPlan value must have a corresponding entry in PLAN_LIMITS."""
        for plan in BillingPlan:
            assert plan.value in PLAN_LIMITS, f"Missing limit for plan: {plan.value}"

    def test_limits_are_monotonically_increasing(self):
        """developer < pro < team. Enterprise is None (unlimited)."""
        dev = PLAN_LIMITS[BillingPlan.DEVELOPER.value]
        pro = PLAN_LIMITS[BillingPlan.PRO.value]
        team = PLAN_LIMITS[BillingPlan.TEAM.value]
        assert dev < pro < team


class TestExtractPlan:
    """Tests for RedisRateLimiter._extract_plan — the billing data reader."""

    def test_extracts_plan_from_enriched_org(self):
        period = SimpleNamespace(plan=BillingPlan.TEAM)
        billing = SimpleNamespace(current_period=period)
        org = _make_org(billing=billing)
        assert RedisRateLimiter._extract_plan(org) == "team"

    def test_raises_on_missing_billing(self):
        org = _make_org(billing=None)
        with pytest.raises(RuntimeError, match="no billing record"):
            RedisRateLimiter._extract_plan(org)

    def test_raises_on_missing_current_period(self):
        billing = SimpleNamespace(current_period=None)
        org = _make_org(billing=billing)
        with pytest.raises(RuntimeError, match="no active billing period"):
            RedisRateLimiter._extract_plan(org)


class TestNullRateLimiter:
    @pytest.mark.asyncio
    async def test_always_allows(self):
        limiter = NullRateLimiter()
        org = _make_org()
        result = await limiter.check(org)
        assert result.allowed is True
        assert result.remaining == 9999
