"""Fake usage repository for testing."""

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.models.usage import Usage


class FakeUsageRepository:
    """In-memory fake for UsageRepositoryProtocol."""

    def __init__(self) -> None:
        """Initialize with empty store and call log."""
        self._store: list[Usage] = []
        self._calls: list[tuple] = []

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
