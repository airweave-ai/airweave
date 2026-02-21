"""Fake sync lifecycle service for testing."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.sources.types import SourceRegistryEntry
from airweave.domains.syncs.types import SyncProvisionResult
from airweave.schemas.source_connection import ScheduleConfig, SourceConnectionJob


class FakeSyncLifecycleService:
    """In-memory fake for SyncLifecycleServiceProtocol."""

    def __init__(self) -> None:
        """Initialize with empty state."""
        self._calls: list[tuple] = []
        self._provision_result: Optional[SyncProvisionResult] = None
        self._run_result: Optional[SourceConnectionJob] = None
        self._jobs: dict[UUID, List[SourceConnectionJob]] = {}
        self._cancel_result: Optional[SourceConnectionJob] = None
        self._should_raise: Optional[Exception] = None

    def set_provision_result(self, result: Optional[SyncProvisionResult]) -> None:
        """Configure provision_sync() return value."""
        self._provision_result = result

    def set_run_result(self, result: SourceConnectionJob) -> None:
        """Configure run() return value."""
        self._run_result = result

    def seed_jobs(self, sc_id: UUID, jobs: List[SourceConnectionJob]) -> None:
        """Seed jobs returned by get_jobs."""
        self._jobs[sc_id] = jobs

    def set_cancel_result(self, result: SourceConnectionJob) -> None:
        """Configure cancel_job() return value."""
        self._cancel_result = result

    def set_error(self, error: Exception) -> None:
        """Make all subsequent calls raise this error."""
        self._should_raise = error

    async def provision_sync(
        self,
        db: AsyncSession,
        *,
        name: str,
        source_connection_id: UUID,
        destination_connection_ids: List[UUID],
        collection_id: UUID,
        collection_readable_id: str,
        source_entry: SourceRegistryEntry,
        schedule_config: Optional[ScheduleConfig],
        run_immediately: bool,
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> Optional[SyncProvisionResult]:
        """Record call and return canned result."""
        self._calls.append(("provision_sync", name, source_connection_id, collection_id))
        if self._should_raise:
            raise self._should_raise
        return self._provision_result

    async def run(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: ApiContext,
        force_full_sync: bool = False,
    ) -> SourceConnectionJob:
        """Record call and return canned result."""
        self._calls.append(("run", db, id, ctx, force_full_sync))
        if self._should_raise:
            raise self._should_raise
        if self._run_result is None:
            raise RuntimeError("FakeSyncLifecycleService.run_result not configured")
        return self._run_result

    async def get_jobs(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: ApiContext,
        limit: int = 100,
    ) -> List[SourceConnectionJob]:
        """Record call and return seeded jobs."""
        self._calls.append(("get_jobs", db, id, ctx, limit))
        if self._should_raise:
            raise self._should_raise
        return self._jobs.get(id, [])[:limit]

    async def cancel_job(
        self,
        db: AsyncSession,
        *,
        source_connection_id: UUID,
        job_id: UUID,
        ctx: ApiContext,
    ) -> SourceConnectionJob:
        """Record call and return canned result."""
        self._calls.append(("cancel_job", db, source_connection_id, job_id, ctx))
        if self._should_raise:
            raise self._should_raise
        if self._cancel_result is None:
            raise RuntimeError("FakeSyncLifecycleService.cancel_result not configured")
        return self._cancel_result
