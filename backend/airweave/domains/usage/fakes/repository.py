"""Fake usage repository for testing."""

from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.domains.usage.types import ActionType
from airweave.models.usage import Usage


class FakeUsageRepository:
    """In-memory fake for UsageRepositoryProtocol."""

    def __init__(self) -> None:
        """Initialize empty in-memory stores."""
        self._current: dict[UUID, Usage] = {}  # org_id -> current usage record
        self._by_period: dict[UUID, Usage] = {}  # billing_period_id -> usage record
        self._all: dict[UUID, list[Usage]] = {}  # org_id -> all usage records
        self._store: list[Usage] = []
        self._calls: list[tuple] = []

    def seed_current(self, organization_id: UUID, usage: Usage) -> None:
        """Set the current usage record for an organization."""
        self._current[organization_id] = usage

    def seed_by_period(self, billing_period_id: UUID, usage: Usage) -> None:
        """Set a usage record for a billing period."""
        self._by_period[billing_period_id] = usage

    def seed_all(self, organization_id: UUID, records: list[Usage]) -> None:
        """Set all usage records for an organization."""
        self._all[organization_id] = records

    def call_count(self, method: str) -> int:
        """Return the number of times a method was called."""
        return sum(1 for name, *_ in self._calls if name == method)

    async def create(
        self, db: AsyncSession, *, obj_in: object, ctx: object, uow: object = None
    ) -> Usage:
        """Create a usage record (fake)."""
        self._calls.append(("create", db, obj_in, ctx, uow))
        usage = Usage(
            id=uuid4(),
            organization_id=obj_in.organization_id,  # type: ignore[union-attr]
            billing_period_id=obj_in.billing_period_id,  # type: ignore[union-attr]
        )
        self._store.append(usage)
        return usage

    async def get_current_usage(
        self, db: AsyncSession, *, organization_id: UUID
    ) -> Optional[Usage]:
        """Get the current usage record for an organization."""
        self._calls.append(("get_current_usage", db, organization_id))
        return self._current.get(organization_id)

    async def increment_usage(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        increments: dict[ActionType, int],
    ) -> Optional[Usage]:
        """Increment usage counters in memory."""
        self._calls.append(("increment_usage", db, organization_id, increments))
        usage = self._current.get(organization_id)
        if usage is None:
            return None
        for action_type, amount in increments.items():
            field = action_type.value
            current = getattr(usage, field, 0) or 0
            setattr(usage, field, current + amount)
        return usage

    async def get_by_billing_period(
        self, db: AsyncSession, *, billing_period_id: UUID
    ) -> Optional[Usage]:
        """Get usage record by billing period ID."""
        self._calls.append(("get_by_billing_period", db, billing_period_id))
        return self._by_period.get(billing_period_id)

    async def get_all_by_organization(
        self, db: AsyncSession, *, organization_id: UUID
    ) -> list[Usage]:
        """Get all usage records for an organization."""
        self._calls.append(("get_all_by_organization", db, organization_id))
        return self._all.get(organization_id, [])

    async def get_current_usage_for_orgs(
        self, db: AsyncSession, *, organization_ids: list[UUID]
    ) -> dict[UUID, Usage]:
        """Get current usage for multiple organizations."""
        self._calls.append(("get_current_usage_for_orgs", db, organization_ids))
        return {oid: self._current[oid] for oid in organization_ids if oid in self._current}
