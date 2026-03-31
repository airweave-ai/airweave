"""Fake sync service for testing — matches unified SyncServiceProtocol."""

from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.context import BaseContext
from airweave.core.shared_models import SyncStatus
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.sources.types import SourceRegistryEntry
from airweave.domains.sync_pipeline.config import SyncConfig
from airweave.domains.syncs.protocols import SyncServiceProtocol
from airweave.domains.syncs.types import SyncProvisionResult, SyncTransitionResult
from airweave.schemas.source_connection import ScheduleConfig


class FakeSyncService(SyncServiceProtocol):
    """In-memory fake for the unified SyncServiceProtocol."""

    def __init__(self) -> None:
        self._calls: list[tuple] = []
        self._create_result: Optional[SyncProvisionResult] = None
        self._get_result: Optional[schemas.Sync] = None
        self._trigger_run_result: Optional[Tuple[schemas.Sync, schemas.SyncJob]] = None
        self._jobs: Dict[UUID, List[schemas.SyncJob]] = {}
        self._cancel_result: Optional[schemas.SyncJob] = None
        self._resolve_dest_ids: Optional[List[UUID]] = None
        self._run_result: Optional[schemas.Sync] = None
        self._should_raise: Optional[Exception] = None

    # -- Configuration helpers --

    def set_create_result(self, result: SyncProvisionResult) -> None:
        self._create_result = result

    def set_get_result(self, result: schemas.Sync) -> None:
        self._get_result = result

    def set_trigger_run_result(self, sync: schemas.Sync, job: schemas.SyncJob) -> None:
        self._trigger_run_result = (sync, job)

    def seed_jobs(self, sync_id: UUID, jobs: List[schemas.SyncJob]) -> None:
        self._jobs[sync_id] = jobs

    def set_cancel_result(self, result: schemas.SyncJob) -> None:
        self._cancel_result = result

    def set_resolve_dest_ids(self, ids: List[UUID]) -> None:
        self._resolve_dest_ids = ids

    def set_run_result(self, result: schemas.Sync) -> None:
        self._run_result = result

    def set_error(self, error: Exception) -> None:
        self._should_raise = error

    # -- Lifecycle --

    async def create(
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
    ) -> SyncProvisionResult:
        self._calls.append(("create", name, source_connection_id, collection_id))
        if self._should_raise:
            raise self._should_raise
        if self._create_result is None:
            raise RuntimeError("FakeSyncService.create_result not configured")
        return self._create_result

    async def get(self, db: AsyncSession, *, sync_id: UUID, ctx: BaseContext) -> schemas.Sync:
        self._calls.append(("get", sync_id))
        if self._should_raise:
            raise self._should_raise
        if self._get_result is None:
            raise ValueError(f"Sync {sync_id} not found")
        return self._get_result

    async def pause(
        self, sync_id: UUID, ctx: BaseContext, *, reason: str = ""
    ) -> SyncTransitionResult:
        self._calls.append(("pause", sync_id, reason))
        if self._should_raise:
            raise self._should_raise
        return SyncTransitionResult(
            applied=True, previous=SyncStatus.ACTIVE, current=SyncStatus.PAUSED
        )

    async def resume(
        self, sync_id: UUID, ctx: BaseContext, *, reason: str = ""
    ) -> SyncTransitionResult:
        self._calls.append(("resume", sync_id, reason))
        if self._should_raise:
            raise self._should_raise
        return SyncTransitionResult(
            applied=True, previous=SyncStatus.PAUSED, current=SyncStatus.ACTIVE
        )

    async def delete(
        self,
        db: AsyncSession,
        *,
        sync_id: UUID,
        collection_id: UUID,
        organization_id: UUID,
        ctx: ApiContext,
        cancel_timeout_seconds: int = 15,
    ) -> None:
        self._calls.append(("delete", sync_id, collection_id, organization_id))
        if self._should_raise:
            raise self._should_raise

    # -- Jobs --

    async def resolve_destination_ids(self, db: AsyncSession, ctx: ApiContext) -> List[UUID]:
        self._calls.append(("resolve_destination_ids",))
        if self._should_raise:
            raise self._should_raise
        if self._resolve_dest_ids is not None:
            return self._resolve_dest_ids
        from airweave.core.constants.reserved_ids import NATIVE_VESPA_UUID

        return [NATIVE_VESPA_UUID]

    async def trigger_run(
        self,
        db: AsyncSession,
        *,
        sync_id: UUID,
        collection: schemas.CollectionRecord,
        connection: schemas.Connection,
        ctx: ApiContext,
        force_full_sync: bool = False,
    ) -> Tuple[schemas.Sync, schemas.SyncJob]:
        self._calls.append(("trigger_run", sync_id))
        if self._should_raise:
            raise self._should_raise
        if self._trigger_run_result is None:
            raise RuntimeError("FakeSyncService.trigger_run_result not configured")
        return self._trigger_run_result

    async def get_jobs(
        self, db: AsyncSession, *, sync_id: UUID, ctx: ApiContext, limit: int = 100
    ) -> List[schemas.SyncJob]:
        self._calls.append(("get_jobs", sync_id, limit))
        if self._should_raise:
            raise self._should_raise
        return self._jobs.get(sync_id, [])[:limit]

    async def cancel_job(
        self, db: AsyncSession, *, job_id: UUID, ctx: ApiContext
    ) -> schemas.SyncJob:
        self._calls.append(("cancel_job", job_id))
        if self._should_raise:
            raise self._should_raise
        if self._cancel_result is None:
            raise RuntimeError("FakeSyncService.cancel_result not configured")
        return self._cancel_result

    async def validate_force_full_sync(
        self, db: AsyncSession, sync_id: UUID, ctx: ApiContext
    ) -> None:
        self._calls.append(("validate_force_full_sync", sync_id))

    # -- Execution --

    async def run(
        self,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.CollectionRecord,
        source_connection: schemas.Connection,
        ctx: ApiContext,
        force_full_sync: bool = False,
        execution_config: Optional[SyncConfig] = None,
        access_token: Optional[str] = None,
    ) -> schemas.Sync:
        self._calls.append(("run", sync, sync_job))
        if self._should_raise:
            raise self._should_raise
        return self._run_result or sync
