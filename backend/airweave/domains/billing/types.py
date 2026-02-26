"""Billing domain types and shared pure functions.

Types, constants, and pure business logic that multiple billing components
depend on (service, webhook handler, operations, endpoints).
Extracted from billing/plan_logic.py.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from airweave.schemas.organization_billing import BillingPlan


class PlanRank(Enum):
    """Plan hierarchy for upgrade/downgrade decisions."""

    DEVELOPER = 0
    PRO = 1
    TEAM = 2
    ENTERPRISE = 3

    @classmethod
    def from_plan(cls, plan: BillingPlan) -> "PlanRank":
        """Convert BillingPlan to PlanRank."""
        mapping = {
            BillingPlan.DEVELOPER: cls.DEVELOPER,
            BillingPlan.PRO: cls.PRO,
            BillingPlan.TEAM: cls.TEAM,
            BillingPlan.ENTERPRISE: cls.ENTERPRISE,
        }
        return mapping.get(plan, cls.DEVELOPER)


class ChangeType(Enum):
    """Type of plan change."""

    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"
    SAME = "same"
    REACTIVATION = "reactivation"


@dataclass
class PlanChangeContext:
    """Context for plan change decisions."""

    current_plan: BillingPlan
    target_plan: BillingPlan
    has_payment_method: bool
    is_canceling: bool
    pending_plan: Optional[BillingPlan] = None
    current_period_end: Optional[datetime] = None


@dataclass
class PlanChangeDecision:
    """Result of plan change analysis."""

    allowed: bool
    change_type: ChangeType
    requires_checkout: bool
    apply_immediately: bool
    message: str
    new_plan: BillingPlan
    clear_pending: bool = False


@dataclass
class PlanInferenceContext:
    """Context for inferring plan from webhook events."""

    current_plan: BillingPlan
    pending_plan: Optional[BillingPlan]
    is_renewal: bool
    items_changed: bool
    subscription_items: list[str]  # List of price IDs


@dataclass
class InferredPlan:
    """Result of plan inference."""

    plan: BillingPlan
    changed: bool
    reason: str
    should_clear_pending: bool = False


# Plan configuration
PLAN_LIMITS = {
    BillingPlan.DEVELOPER: {
        "max_entities": 50000,
        "max_queries": 500,
        "max_source_connections": 10,
        "max_team_members": 1,
    },
    BillingPlan.PRO: {
        "max_entities": 100000,
        "max_queries": 2000,
        "max_source_connections": 50,
        "max_team_members": 2,
    },
    BillingPlan.TEAM: {
        "max_entities": 1000000,
        "max_queries": 10000,
        "max_source_connections": 1000,
        "max_team_members": 10,
    },
    BillingPlan.ENTERPRISE: {
        "max_entities": None,
        "max_queries": None,
        "max_source_connections": None,
        "max_team_members": None,
    },
}


def is_paid_plan(plan: BillingPlan) -> bool:
    """Check if a plan requires payment."""
    return plan in {BillingPlan.PRO, BillingPlan.TEAM, BillingPlan.ENTERPRISE}


def compare_plans(current: BillingPlan, target: BillingPlan) -> ChangeType:
    """Compare two plans to determine change type."""
    current_rank = PlanRank.from_plan(current)
    target_rank = PlanRank.from_plan(target)

    if target_rank.value > current_rank.value:
        return ChangeType.UPGRADE
    elif target_rank.value < current_rank.value:
        return ChangeType.DOWNGRADE
    else:
        return ChangeType.SAME


def get_plan_limits(plan: BillingPlan) -> dict:
    """Get usage limits for a plan."""
    return PLAN_LIMITS.get(plan, PLAN_LIMITS[BillingPlan.PRO])


def compute_yearly_prepay_amount_cents(plan: BillingPlan) -> int:
    """Compute yearly prepay amount in cents.

    Rules: 12 months at current monthly price with 20% discount.
    """
    if plan == BillingPlan.PRO:
        return int(12 * 2000 * 0.8)
    if plan == BillingPlan.TEAM:
        return int(12 * 29900 * 0.8)
    raise ValueError("Yearly prepay only supported for pro and team plans")


def coupon_percent_off_for_yearly_prepay(plan: BillingPlan) -> int:
    """Return coupon percent_off for yearly prepay discount."""
    if plan in {BillingPlan.PRO, BillingPlan.TEAM}:
        return 20
    raise ValueError("Yearly prepay only supported for pro and team plans")
