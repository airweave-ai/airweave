"""Fake sync service for testing."""

from uuid import UUID

from airweave import schemas
from airweave.core.context import BaseContext


class FakeSyncService:
    """In-memory fake for SyncServiceProtocol."""

    def __init__(self) -> None:
        """Initialize with empty call log."""
        self._calls: list[tuple] = []
        self._result: schemas.Sync | None = None

    def set_result(self, result: schemas.Sync) -> None:
        """Configure the sync returned by run()."""
        self._result = result

    async def run(
        self,
        sync_id: UUID,
        sync_job_id: UUID,
        ctx: BaseContext,
        force_full_sync: bool = False,
    ) -> schemas.Sync:
        """Record call and return canned result."""
        self._calls.append(("run", sync_id, sync_job_id, force_full_sync))
        if self._result is not None:
            return self._result
        raise ValueError("FakeSyncService.set_result() not called")
