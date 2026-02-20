"""Fake sync job repository for testing."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.sync_job import SyncJob
from airweave.schemas.sync_job import SyncJobCreate


class FakeSyncJobRepository:
    """In-memory fake for SyncJobRepositoryProtocol."""

    def __init__(self) -> None:
        """Initialize with empty stores."""
        self._store: dict[UUID, SyncJob] = {}
        self._last_jobs: dict[UUID, SyncJob] = {}
        self._by_sync: dict[UUID, list[SyncJob]] = {}
        self._calls: list[tuple] = []
        self._created: list[SyncJob] = []

    def seed(self, id: UUID, job: SyncJob) -> None:
        """Seed a sync job by ID."""
        self._store[id] = job

    def seed_last_job(self, sync_id: UUID, job: SyncJob) -> None:
        """Seed a last job for a given sync_id."""
        self._last_jobs[sync_id] = job

    def seed_jobs_for_sync(self, sync_id: UUID, jobs: list[SyncJob]) -> None:
        """Seed all jobs for a given sync_id."""
        self._by_sync[sync_id] = jobs

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[SyncJob]:
        """Return seeded job by ID or None."""
        self._calls.append(("get", db, id, ctx))
        return self._store.get(id)

    async def get_latest_by_sync_id(self, db: AsyncSession, sync_id: UUID) -> Optional[SyncJob]:
        """Return seeded last job or None."""
        self._calls.append(("get_latest_by_sync_id", db, sync_id))
        return self._last_jobs.get(sync_id)

    async def get_active_for_sync(
        self, db: AsyncSession, sync_id: UUID, ctx: ApiContext
    ) -> List[SyncJob]:
        """Return seeded active jobs for the sync."""
        self._calls.append(("get_active_for_sync", db, sync_id, ctx))
        jobs = self._by_sync.get(sync_id, [])
        return [j for j in jobs if j.status in ("PENDING", "RUNNING", "CANCELLING")]

    async def get_all_by_sync_id(
        self, db: AsyncSession, sync_id: UUID, ctx: ApiContext
    ) -> List[SyncJob]:
        """Return all seeded jobs for the sync."""
        self._calls.append(("get_all_by_sync_id", db, sync_id, ctx))
        return self._by_sync.get(sync_id, [])

    async def create(
        self,
        db: AsyncSession,
        obj_in: SyncJobCreate,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> SyncJob:
        """Create a fake SyncJob from the schema and store it."""
        self._calls.append(("create", db, obj_in, ctx, uow))
        job = SyncJob(
            **obj_in.model_dump(),
            organization_id=ctx.organization.id,
        )
        self._store[job.id] = job
        self._created.append(job)
        return job
