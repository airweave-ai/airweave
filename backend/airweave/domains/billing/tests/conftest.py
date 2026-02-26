"""Billing domain test fixtures and helpers.

Provides pre-built helpers for ApiContext, ORM models, service wiring,
and Stripe event shapes — following the pattern from domains/sources/tests/.
"""

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from airweave.adapters.payment.fake import FakePaymentGateway, _obj
from airweave.api.context import ApiContext
from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod
from airweave.domains.billing.fakes.operations import FakeBillingOperations
from airweave.domains.billing.fakes.repository import (
    FakeBillingPeriodRepository,
    FakeOrganizationBillingRepository,
)
from airweave.domains.billing.service import BillingService
from airweave.domains.billing.webhook_processor import BillingWebhookProcessor
from airweave.domains.organizations.fakes.repository import FakeOrganizationRepository
from airweave.models.billing_period import BillingPeriod
from airweave.models.organization_billing import OrganizationBilling
from airweave.schemas.billing_period import BillingPeriodStatus
from airweave.schemas.organization import Organization
from airweave.schemas.organization_billing import BillingPlan, BillingStatus

# Default test IDs
DEFAULT_ORG_ID = UUID("00000000-0000-0000-0000-000000000001")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx(
    org_id: UUID = DEFAULT_ORG_ID,
    auth_method: AuthMethod = AuthMethod.SYSTEM,
) -> ApiContext:
    """Build a minimal ApiContext for tests."""
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
    """Return an OrganizationBilling ORM model with sensible defaults."""
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
    """Return a BillingPeriod ORM model with sensible defaults."""
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=uuid4(),
        created_at=now,
        modified_at=now,
        organization_id=org_id,
        period_start=now,
        period_end=now + timedelta(days=30),
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


def _make_org_model(org_id: UUID = DEFAULT_ORG_ID, **overrides: Any) -> Any:
    """Return a minimal Organization ORM model for seeding FakeOrganizationRepository."""
    from airweave.models.organization import Organization as OrgModel

    now = datetime.now(timezone.utc)
    defaults = dict(
        id=org_id,
        name="Test Org",
        created_at=now,
        modified_at=now,
    )
    defaults.update(overrides)
    return OrgModel(**defaults)


def _make_service(
    *,
    payment_gateway: Optional[FakePaymentGateway] = None,
    billing_repo: Optional[FakeOrganizationBillingRepository] = None,
    period_repo: Optional[FakeBillingPeriodRepository] = None,
    billing_ops: Optional[FakeBillingOperations] = None,
    org_repo: Optional[FakeOrganizationRepository] = None,
) -> tuple[
    BillingService,
    FakePaymentGateway,
    FakeOrganizationBillingRepository,
    FakeBillingPeriodRepository,
    FakeBillingOperations,
    FakeOrganizationRepository,
]:
    """Build a BillingService wired to fakes. Returns (service, *fakes)."""
    gw = payment_gateway or FakePaymentGateway()
    br = billing_repo or FakeOrganizationBillingRepository()
    pr = period_repo or FakeBillingPeriodRepository()
    bo = billing_ops or FakeBillingOperations()
    org = org_repo or FakeOrganizationRepository()
    svc = BillingService(
        payment_gateway=gw,
        billing_repo=br,
        period_repo=pr,
        billing_ops=bo,
        org_repo=org,
    )
    return svc, gw, br, pr, bo, org


def _make_webhook_processor(
    *,
    payment_gateway: Optional[FakePaymentGateway] = None,
    billing_repo: Optional[FakeOrganizationBillingRepository] = None,
    period_repo: Optional[FakeBillingPeriodRepository] = None,
    billing_ops: Optional[FakeBillingOperations] = None,
    org_repo: Optional[FakeOrganizationRepository] = None,
) -> tuple[
    BillingWebhookProcessor,
    FakePaymentGateway,
    FakeOrganizationBillingRepository,
    FakeBillingPeriodRepository,
    FakeBillingOperations,
    FakeOrganizationRepository,
]:
    """Build a BillingWebhookProcessor wired to fakes. Returns (processor, *fakes)."""
    gw = payment_gateway or FakePaymentGateway()
    br = billing_repo or FakeOrganizationBillingRepository()
    pr = period_repo or FakeBillingPeriodRepository()
    bo = billing_ops or FakeBillingOperations()
    org = org_repo or FakeOrganizationRepository()
    proc = BillingWebhookProcessor(
        payment_gateway=gw,
        billing_repo=br,
        period_repo=pr,
        billing_ops=bo,
        org_repo=org,
    )
    return proc, gw, br, pr, bo, org


def _make_stripe_event(
    event_type: str,
    data_object: Any,
    event_id: str = "evt_test",
    **extra_data: Any,
) -> _obj:
    """Build a minimal Stripe event attribute-bag."""
    data = _obj(object=data_object, **extra_data)
    return _obj(type=event_type, id=event_id, data=data)


def _make_subscription_obj(**overrides: Any) -> _obj:
    """Build a fake Stripe subscription attribute-bag with defaults."""
    now_ts = int(time.time())
    defaults = dict(
        id="sub_test",
        status="active",
        current_period_start=now_ts,
        current_period_end=now_ts + 30 * 86400,
        cancel_at_period_end=False,
        items=_obj(data=[_obj(id="si_test", price=_obj(id="price_pro"))]),
        metadata={"organization_id": str(DEFAULT_ORG_ID), "plan": "pro"},
        default_payment_method="pm_test",
    )
    defaults.update(overrides)
    return _obj(**defaults)


def _make_invoice_obj(**overrides: Any) -> _obj:
    """Build a fake Stripe invoice attribute-bag."""
    defaults = dict(
        id="inv_test",
        customer="cus_test",
        subscription="sub_test",
        amount_due=2000,
        amount_paid=2000,
        currency="usd",
        status_transitions={"paid_at": str(int(time.time()))},
    )
    defaults.update(overrides)
    return _obj(**defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx():
    """ApiContext with default org and system auth."""
    return _make_ctx()


@pytest.fixture
def db():
    """AsyncMock database session — fakes ignore it."""
    return AsyncMock()
