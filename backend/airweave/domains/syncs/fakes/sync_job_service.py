"""Fake sync job service for testing."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from airweave.api.context import ApiContext
from airweave.core.shared_models import SyncJobStatus
from airweave.platform.sync.pipeline.entity_tracker import SyncStats


class FakeSyncJobService:
    """In-memory fake for SyncJobServiceProtocol."""

    def __init__(self) -> None:
        """Initialize with empty call log."""
        self._calls: list[tuple] = []
        self._should_raise: Optional[Exception] = None

    def set_error(self, error: Exception) -> None:
        """Make all subsequent calls raise this error."""
        self._should_raise = error

    async def update_status(
        self,
        sync_job_id: UUID,
        status: SyncJobStatus,
        ctx: ApiContext,
        stats: Optional[SyncStats] = None,
        error: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        failed_at: Optional[datetime] = None,
    ) -> None:
        """Record call."""
        self._calls.append(
            (
                "update_status",
                sync_job_id,
                status,
                ctx,
                stats,
                error,
                started_at,
                completed_at,
                failed_at,
            )
        )
        if self._should_raise:
            raise self._should_raise
