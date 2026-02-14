"""Fake sync service for testing."""

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID


class FakeSyncService:
    """In-memory fake for SyncServiceProtocol."""

    def __init__(self, should_raise: Optional[Exception] = None) -> None:
        self._should_raise = should_raise
        self._last_sync_jobs: dict[UUID, Any] = {}
        self._sync_jobs: dict[UUID, List[Any]] = {}
        self._trigger_results: dict[UUID, Tuple[Any, Any]] = {}

    def _maybe_raise(self) -> None:
        if self._should_raise:
            raise self._should_raise

    async def list_sync_jobs(self, db: Any, ctx: Any, sync_id: UUID, limit: int = 100) -> List[Any]:
        self._maybe_raise()
        return self._sync_jobs.get(sync_id, [])[:limit]

    async def trigger_sync_run(
        self,
        db: Any,
        sync_id: UUID,
        ctx: Any,
        execution_config: Optional[Dict[str, Any]] = None,
        sync_metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Any, Any]:
        self._maybe_raise()
        return self._trigger_results.get(sync_id, (None, None))

    async def get_last_sync_job(self, db: Any, ctx: Any, sync_id: UUID) -> Optional[Any]:
        self._maybe_raise()
        return self._last_sync_jobs.get(sync_id)

    def seed_last_job(self, sync_id: UUID, job: Any) -> None:
        self._last_sync_jobs[sync_id] = job

    def seed_jobs(self, sync_id: UUID, jobs: List[Any]) -> None:
        self._sync_jobs[sync_id] = jobs

    def seed_trigger_result(self, sync_id: UUID, sync: Any, sync_job: Any) -> None:
        self._trigger_results[sync_id] = (sync, sync_job)

    def set_should_raise(self, exc: Optional[Exception]) -> None:
        self._should_raise = exc

    def clear(self) -> None:
        self._should_raise = None
        self._last_sync_jobs.clear()
        self._sync_jobs.clear()
        self._trigger_results.clear()
