"""Fake billing repositories for testing."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.models import OrganizationBilling
from airweave.models.billing_period import BillingPeriod


class FakeOrganizationBillingRepository:
    """In-memory fake for OrganizationBillingRepositoryProtocol."""

    def __init__(self) -> None:
        """Initialize with empty store and call log."""
        self._store: dict[UUID, OrganizationBilling] = {}
        self._calls: list[tuple] = []

    def seed(self, organization_id: UUID, obj: OrganizationBilling) -> None:
        """Populate store with test data."""
        self._store[organization_id] = obj

    async def get_by_org_id(
        self, db: AsyncSession, *, organization_id: UUID
    ) -> Optional[OrganizationBilling]:
        """Get billing record by organization ID."""
        self._calls.append(("get_by_org_id", db, organization_id))
        return self._store.get(organization_id)

    async def get_by_stripe_subscription_id(
        self, db: AsyncSession, *, stripe_subscription_id: str
    ) -> Optional[OrganizationBilling]:
        """Get billing record by Stripe subscription ID."""
        self._calls.append(("get_by_stripe_subscription_id", db, stripe_subscription_id))
        for obj in self._store.values():
            if obj.stripe_subscription_id == stripe_subscription_id:
                return obj
        return None

    async def get_by_stripe_customer_id(
        self, db: AsyncSession, *, stripe_customer_id: str
    ) -> Optional[OrganizationBilling]:
        """Get billing record by Stripe customer ID."""
        self._calls.append(("get_by_stripe_customer_id", db, stripe_customer_id))
        for obj in self._store.values():
            if obj.stripe_customer_id == stripe_customer_id:
                return obj
        return None

    async def create(
        self, db: AsyncSession, *, obj_in: object, ctx: object, uow: object = None
    ) -> OrganizationBilling:
        """Create a billing record (fake)."""
        self._calls.append(("create", db, obj_in, ctx, uow))
        if hasattr(obj_in, "organization_id"):
            self._store[obj_in.organization_id] = obj_in  # type: ignore[assignment]
        return obj_in  # type: ignore[return-value]

    async def update(
        self, db: AsyncSession, *, db_obj: OrganizationBilling, obj_in: object, ctx: object
    ) -> OrganizationBilling:
        """Update a billing record (fake)."""
        self._calls.append(("update", db, db_obj, obj_in, ctx))
        if hasattr(obj_in, "model_dump"):
            updates = obj_in.model_dump(exclude_unset=True)
        elif isinstance(obj_in, dict):
            updates = obj_in
        else:
            updates = {}
        for key, value in updates.items():
            setattr(db_obj, key, value)
        return db_obj


class FakeBillingPeriodRepository:
    """In-memory fake for BillingPeriodRepositoryProtocol."""

    def __init__(self) -> None:
        """Initialize with empty store and call log."""
        self._store: list[BillingPeriod] = []
        self._calls: list[tuple] = []

    def seed(self, obj: BillingPeriod) -> None:
        """Populate store with test data."""
        self._store.append(obj)

    async def get(self, db: AsyncSession, *, id: UUID, ctx: object) -> Optional[BillingPeriod]:
        """Get a billing period by ID."""
        self._calls.append(("get", db, id))
        for p in self._store:
            if p.id == id:
                return p
        return None

    async def create(
        self, db: AsyncSession, *, obj_in: object, ctx: object, uow: object = None
    ) -> BillingPeriod:
        """Create a billing period (fake)."""
        self._calls.append(("create", db, obj_in, ctx, uow))
        period = BillingPeriod(
            id=uuid4(),
            organization_id=obj_in.organization_id,  # type: ignore[union-attr]
            period_start=obj_in.period_start,  # type: ignore[union-attr]
            period_end=obj_in.period_end,  # type: ignore[union-attr]
            plan=obj_in.plan,  # type: ignore[union-attr]
            status=obj_in.status,  # type: ignore[union-attr]
            created_from=obj_in.created_from,  # type: ignore[union-attr]
            stripe_subscription_id=getattr(obj_in, "stripe_subscription_id", None),
            previous_period_id=getattr(obj_in, "previous_period_id", None),
        )
        self._store.append(period)
        return period

    async def get_current_period(
        self, db: AsyncSession, *, organization_id: UUID
    ) -> Optional[BillingPeriod]:
        """Get the current active billing period for an organization."""
        self._calls.append(("get_current_period", db, organization_id))
        for p in self._store:
            if p.organization_id == organization_id:
                return p
        return None

    async def get_current_period_at(
        self, db: AsyncSession, *, organization_id: UUID, at: datetime
    ) -> Optional[BillingPeriod]:
        """Get the active billing period for an organization at a specific time."""
        self._calls.append(("get_current_period_at", db, organization_id, at))
        for p in self._store:
            if p.organization_id == organization_id and p.period_start <= at < p.period_end:
                return p
        return None

    async def get_previous_periods(
        self, db: AsyncSession, *, organization_id: UUID, limit: int = 6
    ) -> list[BillingPeriod]:
        """Get previous billing periods for an organization."""
        self._calls.append(("get_previous_periods", db, organization_id, limit))
        return [p for p in self._store if p.organization_id == organization_id][:limit]

    async def update(
        self, db: AsyncSession, *, db_obj: BillingPeriod, obj_in: dict, ctx: object
    ) -> BillingPeriod:
        """Update a billing period (fake)."""
        self._calls.append(("update", db, db_obj, obj_in, ctx))
        for key, value in obj_in.items():
            setattr(db_obj, key, value)
        return db_obj
