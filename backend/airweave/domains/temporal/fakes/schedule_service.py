"""Fake TemporalScheduleService for testing."""

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.temporal.protocols import TemporalScheduleServiceProtocol


class FakeTemporalScheduleService(TemporalScheduleServiceProtocol):
    """In-memory fake for TemporalScheduleServiceProtocol."""

    def __init__(self) -> None:
        """Initialize with empty call log and default schedule ID."""
        self._calls: list[tuple] = []
        self._schedule_id: str = "fake-schedule-id"
        self._should_raise: Optional[Exception] = None

    def set_schedule_id(self, schedule_id: str) -> None:
        """Configure create_or_update_schedule return value."""
        self._schedule_id = schedule_id

    def set_error(self, error: Exception) -> None:
        """Make all subsequent calls raise this error."""
        self._should_raise = error

    async def create_or_update_schedule(
        self,
        sync_id: UUID,
        cron_schedule: str,
        db: AsyncSession,
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> str:
        """Record call and return canned schedule ID."""
        self._calls.append(
            (
                "create_or_update_schedule",
                sync_id,
                cron_schedule,
                db,
                ctx,
                uow,
            )
        )
        if self._should_raise:
            raise self._should_raise
        return self._schedule_id

    async def delete_all_schedules_for_sync(
        self,
        sync_id: UUID,
        db: AsyncSession,
        ctx: ApiContext,
    ) -> None:
        """Record call."""
        self._calls.append(("delete_all_schedules_for_sync", sync_id, db, ctx))
        if self._should_raise:
            raise self._should_raise
