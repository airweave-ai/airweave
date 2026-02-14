"""Fake sync job service for testing."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID


class FakeSyncJobService:
    """In-memory fake for SyncJobServiceProtocol."""

    def __init__(self, should_raise: Optional[Exception] = None) -> None:
        self._should_raise = should_raise
        self.status_updates: list[dict] = []

    def _maybe_raise(self) -> None:
        if self._should_raise:
            raise self._should_raise

    async def update_status(
        self,
        sync_job_id: UUID,
        status: Any,
        ctx: Any,
        stats: Optional[Any] = None,
        error: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        failed_at: Optional[datetime] = None,
    ) -> None:
        self._maybe_raise()
        self.status_updates.append(
            {
                "sync_job_id": sync_job_id,
                "status": status,
                "error": error,
                "completed_at": completed_at,
            }
        )

    def set_should_raise(self, exc: Optional[Exception]) -> None:
        self._should_raise = exc

    def clear(self) -> None:
        self._should_raise = None
        self.status_updates.clear()
