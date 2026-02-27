"""Fake billing operations for testing."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.context import BaseContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.models import Organization
from airweave.schemas.billing_period import BillingPeriodStatus, BillingTransition
from airweave.schemas.organization_billing import BillingPlan


class FakeBillingOperations:
    """In-memory fake for BillingOperationsProtocol."""

    def __init__(self) -> None:
        """Initialize with empty stores and call log."""
        self._periods: list[dict] = []
        self._billing_records: list[dict] = []
        self._calls: list[tuple] = []

    async def create_billing_period(
        self,
        db: AsyncSession,
        organization_id: UUID,
        period_start: datetime,
        period_end: datetime,
        plan: BillingPlan,
        transition: BillingTransition,
        ctx: BaseContext,
        stripe_subscription_id: str,
        previous_period_id: Optional[UUID] = None,
        status: BillingPeriodStatus = BillingPeriodStatus.ACTIVE,
    ) -> object:
        """Create a billing period (fake)."""
        self._calls.append(("create_billing_period", db, organization_id))
        record = {
            "id": uuid4(),
            "organization_id": organization_id,
            "period_start": period_start,
            "period_end": period_end,
            "plan": plan,
            "transition": transition,
            "stripe_subscription_id": stripe_subscription_id,
            "previous_period_id": previous_period_id,
            "status": status,
        }
        self._periods.append(record)
        return record

    async def create_billing_record(
        self,
        db: AsyncSession,
        organization: Organization,
        stripe_customer_id: str,
        billing_email: str,
        ctx: BaseContext,
        uow: UnitOfWork,
    ) -> object:
        """Create a billing record (fake)."""
        self._calls.append(("create_billing_record", db, organization.id))
        record = {
            "id": uuid4(),
            "organization_id": organization.id,
            "stripe_customer_id": stripe_customer_id,
            "billing_email": billing_email,
        }
        self._billing_records.append(record)
        return record
