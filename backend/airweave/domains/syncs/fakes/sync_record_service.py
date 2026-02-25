"""Fake sync record service for testing."""

from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork


class FakeSyncRecordService:
    """In-memory fake for SyncRecordServiceProtocol."""

    def __init__(self) -> None:
        """Initialize with empty state."""
        self._calls: list[tuple] = []
        self._create_result: Optional[Tuple[schemas.Sync, Optional[schemas.SyncJob]]] = None
        self._trigger_result: Optional[Tuple[schemas.Sync, schemas.SyncJob]] = None
        self._resolve_dest_ids: Optional[List[UUID]] = None
        self._should_raise: Optional[Exception] = None

    def set_create_result(
        self, sync: schemas.Sync, sync_job: Optional[schemas.SyncJob] = None
    ) -> None:
        """Configure create_sync return value."""
        self._create_result = (sync, sync_job)

    def set_trigger_result(self, sync: schemas.Sync, sync_job: schemas.SyncJob) -> None:
        """Configure trigger_sync_run return value."""
        self._trigger_result = (sync, sync_job)

    def set_resolve_dest_ids(self, ids: List[UUID]) -> None:
        """Configure resolve_destination_ids return value."""
        self._resolve_dest_ids = ids

    def set_error(self, error: Exception) -> None:
        """Make all subsequent calls raise this error."""
        self._should_raise = error

    async def resolve_destination_ids(
        self,
        db: AsyncSession,
        ctx: ApiContext,
    ) -> List[UUID]:
        """Record call and return canned result."""
        self._calls.append(("resolve_destination_ids",))
        if self._should_raise:
            raise self._should_raise
        if self._resolve_dest_ids is None:
            from airweave.core.constants.reserved_ids import NATIVE_VESPA_UUID

            return [NATIVE_VESPA_UUID]
        return self._resolve_dest_ids

    async def create_sync(
        self,
        db: AsyncSession,
        *,
        name: str,
        source_connection_id: UUID,
        destination_connection_ids: List[UUID],
        cron_schedule: Optional[str],
        run_immediately: bool,
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> Tuple[schemas.Sync, Optional[schemas.SyncJob]]:
        """Record call and return canned result."""
        self._calls.append(
            ("create_sync", name, source_connection_id, cron_schedule, run_immediately)
        )
        if self._should_raise:
            raise self._should_raise
        if self._create_result is None:
            raise RuntimeError("FakeSyncRecordService.create_result not configured")
        return self._create_result

    async def trigger_sync_run(
        self,
        db: AsyncSession,
        sync_id: UUID,
        ctx: ApiContext,
    ) -> Tuple[schemas.Sync, schemas.SyncJob]:
        """Record call and return canned result."""
        self._calls.append(("trigger_sync_run", db, sync_id, ctx))
        if self._should_raise:
            raise self._should_raise
        if self._trigger_result is None:
            raise RuntimeError("FakeSyncRecordService.trigger_result not configured")
        return self._trigger_result
