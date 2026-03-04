"""Unit tests for billing domain types and pure functions."""

from dataclasses import dataclass

import pytest

from airweave.domains.billing.types import (
    PLAN_LIMITS,
    ChangeType,
    PlanRank,
    compare_plans,
    compute_yearly_prepay_amount_cents,
    coupon_percent_off_for_yearly_prepay,
    get_plan_limits,
    is_paid_plan,
)
from airweave.schemas.organization_billing import BillingPlan


# ---------------------------------------------------------------------------
# PlanRank.from_plan
# ---------------------------------------------------------------------------


@dataclass
class RankCase:
    label: str
    plan: BillingPlan
    expected: int


RANK_CASES = [
    RankCase("developer", BillingPlan.DEVELOPER, 0),
    RankCase("pro", BillingPlan.PRO, 1),
    RankCase("team", BillingPlan.TEAM, 2),
    RankCase("enterprise", BillingPlan.ENTERPRISE, 3),
]


@pytest.mark.parametrize("case", RANK_CASES, ids=lambda c: c.label)
def test_plan_rank_from_plan(case: RankCase):
    assert PlanRank.from_plan(case.plan).value == case.expected


# ---------------------------------------------------------------------------
# compare_plans
# ---------------------------------------------------------------------------


@dataclass
class CompareCase:
    label: str
    current: BillingPlan
    target: BillingPlan
    expected: ChangeType


COMPARE_CASES = [
    CompareCase("dev_to_pro", BillingPlan.DEVELOPER, BillingPlan.PRO, ChangeType.UPGRADE),
    CompareCase("pro_to_team", BillingPlan.PRO, BillingPlan.TEAM, ChangeType.UPGRADE),
    CompareCase("dev_to_enterprise", BillingPlan.DEVELOPER, BillingPlan.ENTERPRISE, ChangeType.UPGRADE),
    CompareCase("team_to_dev", BillingPlan.TEAM, BillingPlan.DEVELOPER, ChangeType.DOWNGRADE),
    CompareCase("pro_to_dev", BillingPlan.PRO, BillingPlan.DEVELOPER, ChangeType.DOWNGRADE),
    CompareCase("pro_to_pro", BillingPlan.PRO, BillingPlan.PRO, ChangeType.SAME),
]


@pytest.mark.parametrize("case", COMPARE_CASES, ids=lambda c: c.label)
def test_compare_plans(case: CompareCase):
    assert compare_plans(case.current, case.target) == case.expected


# ---------------------------------------------------------------------------
# is_paid_plan
# ---------------------------------------------------------------------------


@dataclass
class PaidCase:
    plan: BillingPlan
    expected: bool


PAID_CASES = [
    PaidCase(BillingPlan.DEVELOPER, False),
    PaidCase(BillingPlan.PRO, True),
    PaidCase(BillingPlan.TEAM, True),
    PaidCase(BillingPlan.ENTERPRISE, True),
]


@pytest.mark.parametrize("case", PAID_CASES, ids=lambda c: c.plan.value)
def test_is_paid_plan(case: PaidCase):
    assert is_paid_plan(case.plan) == case.expected


# ---------------------------------------------------------------------------
# get_plan_limits
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "plan", [p for p in BillingPlan if p in PLAN_LIMITS], ids=lambda p: p.value
)
def test_get_plan_limits_returns_correct_dict(plan: BillingPlan):
    result = get_plan_limits(plan)
    assert result == PLAN_LIMITS[plan]
    assert "max_entities" in result
    assert "max_queries" in result


def test_get_plan_limits_unknown_defaults_to_pro():
    """Plans not in PLAN_LIMITS (e.g. TRIAL) fall back to PRO limits."""
    result = get_plan_limits(BillingPlan.TRIAL)
    assert result == PLAN_LIMITS[BillingPlan.PRO]


# ---------------------------------------------------------------------------
# compute_yearly_prepay_amount_cents
# ---------------------------------------------------------------------------


def test_yearly_prepay_pro():
    assert compute_yearly_prepay_amount_cents(BillingPlan.PRO) == int(12 * 2000 * 0.8)


def test_yearly_prepay_team():
    assert compute_yearly_prepay_amount_cents(BillingPlan.TEAM) == int(12 * 29900 * 0.8)


def test_yearly_prepay_developer_raises():
    with pytest.raises(ValueError, match="only supported for pro and team"):
        compute_yearly_prepay_amount_cents(BillingPlan.DEVELOPER)


# ---------------------------------------------------------------------------
# coupon_percent_off_for_yearly_prepay
# ---------------------------------------------------------------------------


def test_coupon_percent_off_pro():
    assert coupon_percent_off_for_yearly_prepay(BillingPlan.PRO) == 20


def test_coupon_percent_off_team():
    assert coupon_percent_off_for_yearly_prepay(BillingPlan.TEAM) == 20


def test_coupon_percent_off_developer_raises():
    with pytest.raises(ValueError, match="only supported for pro and team"):
        coupon_percent_off_for_yearly_prepay(BillingPlan.DEVELOPER)
