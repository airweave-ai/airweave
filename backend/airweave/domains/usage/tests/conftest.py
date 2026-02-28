"""Usage domain test fixtures and helpers.

Follows the pattern from domains/billing/tests/.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod
from airweave.domains.billing.fakes.repository import (
    FakeBillingPeriodRepository,
    FakeOrganizationBillingRepository,
)
from airweave.domains.organizations.fakes.repository import FakeUserOrganizationRepository
from airweave.domains.source_connections.fakes.repository import FakeSourceConnectionRepository
from airweave.domains.usage.fakes.repository import FakeUsageRepository
from airweave.domains.usage.limit_checker import UsageLimitChecker
from airweave.models.billing_period import BillingPeriod
from airweave.models.organization_billing import OrganizationBilling
from airweave.models.usage import Usage as UsageModel
from airweave.schemas.billing_period import BillingPeriodStatus
from airweave.schemas.organization import Organization
from airweave.schemas.organization_billing import BillingPlan, BillingStatus

DEFAULT_ORG_ID = UUID("00000000-0000-0000-0000-000000000001")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx(
    org_id: UUID = DEFAULT_ORG_ID,
    auth_method: AuthMethod = AuthMethod.SYSTEM,
):
    """Build a minimal ApiContext for tests."""
    from airweave.api.context import ApiContext

    now = datetime.now(timezone.utc)
    org = Organization(
        id=str(org_id),
        name="Test Org",
        created_at=now,
        modified_at=now,
        enabled_features=[],
    )
    return ApiContext(
        request_id="test-req-001",
        organization=org,
        auth_method=auth_method,
        auth_metadata={},
        logger=logger.with_context(request_id="test-req-001"),
    )


def _make_billing_model(
    org_id: UUID = DEFAULT_ORG_ID, **overrides: Any
) -> OrganizationBilling:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=uuid4(),
        created_at=now,
        modified_at=now,
        organization_id=org_id,
        stripe_customer_id="cus_test",
        stripe_subscription_id="sub_test",
        billing_plan=BillingPlan.PRO.value,
        billing_status=BillingStatus.ACTIVE.value,
        billing_email="test@example.com",
        payment_method_added=True,
        payment_method_id="pm_test",
        cancel_at_period_end=False,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
        trial_ends_at=None,
        grace_period_ends_at=None,
        pending_plan_change=None,
        pending_plan_change_at=None,
        last_payment_status=None,
        last_payment_at=None,
        billing_metadata={},
        has_yearly_prepay=False,
        yearly_prepay_started_at=None,
        yearly_prepay_expires_at=None,
        yearly_prepay_amount_cents=None,
        yearly_prepay_coupon_id=None,
        yearly_prepay_payment_intent_id=None,
    )
    defaults.update(overrides)
    return OrganizationBilling(**defaults)


def _make_period_model(
    org_id: UUID = DEFAULT_ORG_ID, **overrides: Any
) -> BillingPeriod:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=uuid4(),
        created_at=now,
        modified_at=now,
        organization_id=org_id,
        period_start=now - timedelta(days=1),
        period_end=now + timedelta(days=29),
        plan=BillingPlan.PRO.value,
        status=BillingPeriodStatus.ACTIVE.value,
        stripe_subscription_id="sub_test",
        stripe_invoice_id=None,
        amount_cents=None,
        currency=None,
        paid_at=None,
        created_from="initial_signup",
        previous_period_id=None,
    )
    defaults.update(overrides)
    return BillingPeriod(**defaults)


def _make_usage_model(
    org_id: UUID = DEFAULT_ORG_ID,
    billing_period_id: Optional[UUID] = None,
    **overrides: Any,
) -> UsageModel:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=uuid4(),
        created_at=now,
        modified_at=now,
        organization_id=org_id,
        billing_period_id=billing_period_id or uuid4(),
        entities=0,
        queries=0,
    )
    defaults.update(overrides)
    return UsageModel(**defaults)


def _make_checker(
    *,
    usage_repo: Optional[FakeUsageRepository] = None,
    billing_repo: Optional[FakeOrganizationBillingRepository] = None,
    period_repo: Optional[FakeBillingPeriodRepository] = None,
    sc_repo: Optional[FakeSourceConnectionRepository] = None,
    user_org_repo: Optional[FakeUserOrganizationRepository] = None,
) -> tuple[
    UsageLimitChecker,
    FakeUsageRepository,
    FakeOrganizationBillingRepository,
    FakeBillingPeriodRepository,
    FakeSourceConnectionRepository,
    FakeUserOrganizationRepository,
]:
    """Build a UsageLimitChecker wired to fakes. Returns (checker, *fakes)."""
    ur = usage_repo or FakeUsageRepository()
    br = billing_repo or FakeOrganizationBillingRepository()
    pr = period_repo or FakeBillingPeriodRepository()
    sc = sc_repo or FakeSourceConnectionRepository()
    uo = user_org_repo or FakeUserOrganizationRepository()
    checker = UsageLimitChecker(
        usage_repo=ur,
        billing_repo=br,
        period_repo=pr,
        sc_repo=sc,
        user_org_repo=uo,
    )
    return checker, ur, br, pr, sc, uo


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx():
    return _make_ctx()


@pytest.fixture
def db():
    return AsyncMock()
