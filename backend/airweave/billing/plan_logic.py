"""Pure business logic for billing operations.

This module contains all the business rules and logic for billing,
separated from infrastructure concerns like database and Stripe API.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from airweave.schemas.organization_billing import BillingPlan, BillingStatus


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
        "max_entities": 100000,
        "max_queries": 50,
        "max_source_connections": 10,
        "max_team_members": 1,
    },
    BillingPlan.PRO: {
        "max_entities": 500000,
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


def analyze_plan_change(context: PlanChangeContext) -> PlanChangeDecision:
    """Analyze a plan change request and determine the appropriate action.

    This is the core business logic for plan changes, replacing the complex
    conditionals in the original update_subscription_plan.
    """
    # Special case: reactivating a canceled subscription
    if context.is_canceling and context.current_plan == context.target_plan:
        return PlanChangeDecision(
            allowed=True,
            change_type=ChangeType.REACTIVATION,
            requires_checkout=False,
            apply_immediately=True,
            message="Subscription reactivated successfully",
            new_plan=context.current_plan,
        )

    change_type = compare_plans(context.current_plan, context.target_plan)

    # Same plan, no change needed
    if change_type == ChangeType.SAME:
        return PlanChangeDecision(
            allowed=False,
            change_type=change_type,
            requires_checkout=False,
            apply_immediately=False,
            message=f"Already on {context.target_plan} plan",
            new_plan=context.current_plan,
        )

    # Check if payment method is required
    target_is_paid = is_paid_plan(context.target_plan)
    needs_payment_method = target_is_paid and not context.has_payment_method

    if needs_payment_method:
        return PlanChangeDecision(
            allowed=False,
            change_type=change_type,
            requires_checkout=True,
            apply_immediately=False,
            message="Payment method required for upgrade; use checkout-session",
            new_plan=context.current_plan,
        )

    # Upgrade: apply immediately with proration
    if change_type == ChangeType.UPGRADE:
        return PlanChangeDecision(
            allowed=True,
            change_type=change_type,
            requires_checkout=False,
            apply_immediately=True,
            message=f"Successfully upgraded to {context.target_plan} plan",
            new_plan=context.target_plan,
            clear_pending=True,
        )

    # Downgrade: schedule for end of period
    if change_type == ChangeType.DOWNGRADE:
        return PlanChangeDecision(
            allowed=True,
            change_type=change_type,
            requires_checkout=False,
            apply_immediately=False,
            message=f"Subscription will be downgraded to {context.target_plan} "
            "at the end of the current billing period",
            new_plan=context.current_plan,  # Keep current plan until period end
        )

    return PlanChangeDecision(
        allowed=False,
        change_type=change_type,
        requires_checkout=False,
        apply_immediately=False,
        message="Invalid plan change",
        new_plan=context.current_plan,
    )


def infer_plan_from_webhook(
    context: PlanInferenceContext,
    price_id_mapping: dict[str, BillingPlan],
) -> InferredPlan:
    """Infer the new plan from webhook event data.

    This replaces the complex _infer_new_plan logic with a cleaner approach.
    Priority rules:
    1. At renewal with pending change -> use pending plan
    2. At renewal without pending -> use subscription items
    3. On immediate change -> use subscription items
    4. Otherwise -> keep current
    """
    # Extract plans from subscription items
    active_plans = set()
    for price_id in context.subscription_items:
        if price_id in price_id_mapping:
            active_plans.add(price_id_mapping[price_id])

    # Case 1: Renewal with pending plan change
    if context.is_renewal and context.pending_plan:
        return InferredPlan(
            plan=context.pending_plan,
            changed=context.pending_plan != context.current_plan,
            reason="renewal_with_pending_change",
            should_clear_pending=True,
        )

    # Case 2: Renewal without pending change
    if context.is_renewal:
        # If only one plan in items, use it
        if len(active_plans) == 1:
            new_plan = next(iter(active_plans))
            return InferredPlan(
                plan=new_plan,
                changed=new_plan != context.current_plan,
                reason="renewal_single_plan",
            )

        # Multiple or no plans, keep current
        return InferredPlan(
            plan=context.current_plan,
            changed=False,
            reason="renewal_keep_current",
        )

    # Case 3: Immediate items change (not renewal)
    if context.items_changed:
        # Single plan in items
        if len(active_plans) == 1:
            new_plan = next(iter(active_plans))
            return InferredPlan(
                plan=new_plan,
                changed=new_plan != context.current_plan,
                reason="items_change_single_plan",
            )

        # Try to find a plan different from current
        different_plans = active_plans - {context.current_plan}
        if len(different_plans) == 1:
            new_plan = next(iter(different_plans))
            return InferredPlan(
                plan=new_plan,
                changed=True,
                reason="items_change_different_plan",
            )

        # Ambiguous, keep current
        return InferredPlan(
            plan=context.current_plan,
            changed=False,
            reason="items_change_ambiguous",
        )

    # No relevant changes
    return InferredPlan(
        plan=context.current_plan,
        changed=False,
        reason="no_relevant_changes",
    )


def determine_period_transition(
    old_plan: BillingPlan,
    new_plan: BillingPlan,
    is_first_period: bool = False,
) -> str:
    """Determine the type of billing period transition."""
    from airweave.schemas.billing_period import BillingTransition

    if is_first_period:
        return BillingTransition.INITIAL_SIGNUP

    change_type = compare_plans(old_plan, new_plan)

    if change_type == ChangeType.UPGRADE:
        return BillingTransition.UPGRADE
    elif change_type == ChangeType.DOWNGRADE:
        return BillingTransition.DOWNGRADE
    else:
        return BillingTransition.RENEWAL


def should_create_new_period(
    event_type: str,
    plan_changed: bool,
    change_type: ChangeType,
) -> bool:
    """Determine if a new billing period should be created."""
    # Always create period on renewal
    if event_type == "renewal":
        return True

    # Create period only for upgrades on immediate changes
    if event_type == "immediate_change" and change_type == ChangeType.UPGRADE:
        return True

    return False


def calculate_grace_period_end(base_date: datetime, grace_days: int = 7) -> datetime:
    """Calculate grace period end date."""
    from datetime import timedelta

    return base_date + timedelta(days=grace_days)


def get_plan_limits(plan: BillingPlan) -> dict:
    """Get usage limits for a plan."""
    return PLAN_LIMITS.get(plan, PLAN_LIMITS[BillingPlan.PRO])


def needs_billing_setup(
    has_active_subscription: bool,
    status: BillingStatus,
    plan: BillingPlan,
) -> bool:
    """Check if organization needs to complete billing setup."""
    if has_active_subscription:
        return False

    # Paid plans without subscription need setup
    if is_paid_plan(plan) and not has_active_subscription:
        return True

    # Trial expired needs setup
    if status == BillingStatus.TRIAL_EXPIRED:
        return True

    return False


# ------------------------------ Yearly Prepay ------------------------------ #


def compute_yearly_prepay_amount_cents(plan: BillingPlan) -> int:
    """Compute yearly prepay amount in cents.

    Rules: 12 months at current monthly price with 20% discount.
    Pricing is defined externally (Stripe), but we hardcode business expectations
    for validation and UI hints when needed. The Stripe checkout will be the
    ultimate source of truth for the amount actually charged.

    Values per spec:
    - PRO: 12 * 2000 * 0.8 = 19200
    - TEAM: 12 * 29900 * 0.8 = 286,?0 -> 12 * 29900 = 358800; *0.8 = 287040

    We return integers (cents), guarding against unsupported plans.
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
