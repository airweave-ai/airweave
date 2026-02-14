"""Fake temporal schedule service for testing."""

from typing import Any, Optional
from uuid import UUID


class FakeTemporalScheduleService:
    """In-memory fake for TemporalScheduleServiceProtocol."""

    def __init__(self, should_raise: Optional[Exception] = None) -> None:
        self._should_raise = should_raise
        self.schedules_created: list[dict] = []

    def _maybe_raise(self) -> None:
        if self._should_raise:
            raise self._should_raise

    async def create_or_update_schedule(
        self,
        sync_id: UUID,
        cron_schedule: str,
        db: Any,
        ctx: Any,
        uow: Any,
    ) -> str:
        self._maybe_raise()
        self.schedules_created.append(
            {
                "sync_id": sync_id,
                "cron_schedule": cron_schedule,
            }
        )
        return f"schedule-{sync_id}"

    def set_should_raise(self, exc: Optional[Exception]) -> None:
        self._should_raise = exc

    def clear(self) -> None:
        self._should_raise = None
        self.schedules_created.clear()
