"""Table-driven tests for BillingService._analyze_plan_change()."""

from dataclasses import dataclass

import pytest

from airweave.domains.billing.service import BillingService
from airweave.domains.billing.types import ChangeType, PlanChangeContext, PlanChangeDecision
from airweave.schemas.organization_billing import BillingPlan


@dataclass
class AnalyzeCase:
    label: str
    context: PlanChangeContext
    expected_allowed: bool
    expected_change_type: ChangeType
    expected_requires_checkout: bool
    expected_apply_immediately: bool
    expected_clear_pending: bool = False


CASES = [
    AnalyzeCase(
        label="reactivation_pro",
        context=PlanChangeContext(
            current_plan=BillingPlan.PRO,
            target_plan=BillingPlan.PRO,
            has_payment_method=True,
            is_canceling=True,
        ),
        expected_allowed=True,
        expected_change_type=ChangeType.REACTIVATION,
        expected_requires_checkout=False,
        expected_apply_immediately=True,
    ),
    AnalyzeCase(
        label="reactivation_developer",
        context=PlanChangeContext(
            current_plan=BillingPlan.DEVELOPER,
            target_plan=BillingPlan.DEVELOPER,
            has_payment_method=True,
            is_canceling=True,
        ),
        expected_allowed=True,
        expected_change_type=ChangeType.REACTIVATION,
        expected_requires_checkout=False,
        expected_apply_immediately=True,
    ),
    AnalyzeCase(
        label="same_plan_no_change",
        context=PlanChangeContext(
            current_plan=BillingPlan.PRO,
            target_plan=BillingPlan.PRO,
            has_payment_method=True,
            is_canceling=False,
        ),
        expected_allowed=False,
        expected_change_type=ChangeType.SAME,
        expected_requires_checkout=False,
        expected_apply_immediately=False,
    ),
    AnalyzeCase(
        label="upgrade_with_pm",
        context=PlanChangeContext(
            current_plan=BillingPlan.DEVELOPER,
            target_plan=BillingPlan.PRO,
            has_payment_method=True,
            is_canceling=False,
        ),
        expected_allowed=True,
        expected_change_type=ChangeType.UPGRADE,
        expected_requires_checkout=False,
        expected_apply_immediately=True,
        expected_clear_pending=True,
    ),
    AnalyzeCase(
        label="upgrade_no_pm",
        context=PlanChangeContext(
            current_plan=BillingPlan.DEVELOPER,
            target_plan=BillingPlan.PRO,
            has_payment_method=False,
            is_canceling=False,
        ),
        expected_allowed=False,
        expected_change_type=ChangeType.UPGRADE,
        expected_requires_checkout=True,
        expected_apply_immediately=False,
    ),
    AnalyzeCase(
        label="downgrade_team_to_pro",
        context=PlanChangeContext(
            current_plan=BillingPlan.TEAM,
            target_plan=BillingPlan.PRO,
            has_payment_method=True,
            is_canceling=False,
        ),
        expected_allowed=True,
        expected_change_type=ChangeType.DOWNGRADE,
        expected_requires_checkout=False,
        expected_apply_immediately=False,
    ),
    AnalyzeCase(
        label="dev_to_team_with_pm",
        context=PlanChangeContext(
            current_plan=BillingPlan.DEVELOPER,
            target_plan=BillingPlan.TEAM,
            has_payment_method=True,
            is_canceling=False,
        ),
        expected_allowed=True,
        expected_change_type=ChangeType.UPGRADE,
        expected_requires_checkout=False,
        expected_apply_immediately=True,
        expected_clear_pending=True,
    ),
    AnalyzeCase(
        label="dev_to_team_no_pm",
        context=PlanChangeContext(
            current_plan=BillingPlan.DEVELOPER,
            target_plan=BillingPlan.TEAM,
            has_payment_method=False,
            is_canceling=False,
        ),
        expected_allowed=False,
        expected_change_type=ChangeType.UPGRADE,
        expected_requires_checkout=True,
        expected_apply_immediately=False,
    ),
    AnalyzeCase(
        label="team_to_developer",
        context=PlanChangeContext(
            current_plan=BillingPlan.TEAM,
            target_plan=BillingPlan.DEVELOPER,
            has_payment_method=True,
            is_canceling=False,
        ),
        expected_allowed=True,
        expected_change_type=ChangeType.DOWNGRADE,
        expected_requires_checkout=False,
        expected_apply_immediately=False,
    ),
    AnalyzeCase(
        label="pro_to_enterprise_with_pm",
        context=PlanChangeContext(
            current_plan=BillingPlan.PRO,
            target_plan=BillingPlan.ENTERPRISE,
            has_payment_method=True,
            is_canceling=False,
        ),
        expected_allowed=True,
        expected_change_type=ChangeType.UPGRADE,
        expected_requires_checkout=False,
        expected_apply_immediately=True,
        expected_clear_pending=True,
    ),
    AnalyzeCase(
        label="pro_to_enterprise_no_pm",
        context=PlanChangeContext(
            current_plan=BillingPlan.PRO,
            target_plan=BillingPlan.ENTERPRISE,
            has_payment_method=False,
            is_canceling=False,
        ),
        expected_allowed=False,
        expected_change_type=ChangeType.UPGRADE,
        expected_requires_checkout=True,
        expected_apply_immediately=False,
    ),
    AnalyzeCase(
        label="enterprise_to_developer",
        context=PlanChangeContext(
            current_plan=BillingPlan.ENTERPRISE,
            target_plan=BillingPlan.DEVELOPER,
            has_payment_method=True,
            is_canceling=False,
        ),
        expected_allowed=True,
        expected_change_type=ChangeType.DOWNGRADE,
        expected_requires_checkout=False,
        expected_apply_immediately=False,
    ),
    AnalyzeCase(
        label="downgrade_while_canceling",
        context=PlanChangeContext(
            current_plan=BillingPlan.TEAM,
            target_plan=BillingPlan.DEVELOPER,
            has_payment_method=True,
            is_canceling=True,
        ),
        expected_allowed=True,
        expected_change_type=ChangeType.DOWNGRADE,
        expected_requires_checkout=False,
        expected_apply_immediately=False,
    ),
]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.label)
def test_analyze_plan_change(case: AnalyzeCase):
    decision = BillingService._analyze_plan_change(case.context)

    assert decision.allowed == case.expected_allowed, f"allowed: {decision.allowed}"
    assert decision.change_type == case.expected_change_type, f"change_type: {decision.change_type}"
    assert decision.requires_checkout == case.expected_requires_checkout, (
        f"requires_checkout: {decision.requires_checkout}"
    )
    assert decision.apply_immediately == case.expected_apply_immediately, (
        f"apply_immediately: {decision.apply_immediately}"
    )
    assert decision.clear_pending == case.expected_clear_pending, (
        f"clear_pending: {decision.clear_pending}"
    )
