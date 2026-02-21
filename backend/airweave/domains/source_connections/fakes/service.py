"""Fake source connection service for testing."""

from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core.exceptions import NotFoundException
from airweave.domains.source_connections.protocols import (
    SourceConnectionDeletionServiceProtocol,
    SourceConnectionUpdateServiceProtocol,
)
from airweave.domains.syncs.protocols import SyncLifecycleServiceProtocol
from airweave.models.source_connection import SourceConnection
from airweave.schemas.source_connection import (
    SourceConnection as SourceConnectionSchema,
)
from airweave.schemas.source_connection import (
    SourceConnectionCreate,
    SourceConnectionJob,
    SourceConnectionListItem,
    SourceConnectionUpdate,
)


class FakeSourceConnectionService:
    """In-memory fake for SourceConnectionServiceProtocol."""

    def __init__(
        self,
        sync_lifecycle: SyncLifecycleServiceProtocol,
        update_service: Optional[SourceConnectionUpdateServiceProtocol] = None,
        deletion_service: Optional[SourceConnectionDeletionServiceProtocol] = None,
    ) -> None:
        self._store: dict[UUID, SourceConnection] = {}
        self._list_items: List[SourceConnectionListItem] = []
        self._calls: list[tuple[Any, ...]] = []
        self._sync_lifecycle = sync_lifecycle
        self._update_service = update_service
        self._deletion_service = deletion_service

    def seed(self, id: UUID, obj: SourceConnection) -> None:
        self._store[id] = obj

    def seed_list_items(self, items: List[SourceConnectionListItem]) -> None:
        self._list_items = list(items)

    async def get(self, db: AsyncSession, *, id: UUID, ctx: ApiContext) -> SourceConnection:
        self._calls.append(("get", db, id, ctx))
        obj = self._store.get(id)
        if not obj:
            raise NotFoundException("Source connection not found")
        return obj

    async def list(
        self,
        db: AsyncSession,
        *,
        ctx: ApiContext,
        readable_collection_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[SourceConnectionListItem]:
        self._calls.append(("list", db, ctx, readable_collection_id, skip, limit))
        items = self._list_items
        if readable_collection_id is not None:
            items = [i for i in items if i.readable_collection_id == readable_collection_id]
        return items[skip : skip + limit]

    async def create(
        self, db: AsyncSession, obj_in: SourceConnectionCreate, ctx: ApiContext
    ) -> SourceConnection:
        self._calls.append(("create", db, obj_in, ctx))
        raise NotImplementedError("FakeSourceConnectionService.create not implemented")

    async def update(
        self, db: AsyncSession, id: UUID, obj_in: SourceConnectionUpdate, ctx: ApiContext
    ) -> SourceConnectionSchema:
        self._calls.append(("update", db, id, obj_in, ctx))
        if self._update_service:
            return await self._update_service.update(db, id=id, obj_in=obj_in, ctx=ctx)
        raise NotImplementedError("FakeSourceConnectionService.update not wired")

    async def delete(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> SourceConnectionSchema:
        self._calls.append(("delete", db, id, ctx))
        if self._deletion_service:
            return await self._deletion_service.delete(db, id=id, ctx=ctx)
        obj = self._store.get(id)
        if not obj:
            raise NotFoundException("Source connection not found")
        del self._store[id]
        return obj

    async def run(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: ApiContext,
        force_full_sync: bool = False,
    ) -> SourceConnectionJob:
        self._calls.append(("run", db, id, ctx, force_full_sync))
        return await self._sync_lifecycle.run(db, id=id, ctx=ctx, force_full_sync=force_full_sync)

    async def get_jobs(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: ApiContext,
        limit: int = 100,
    ) -> List[SourceConnectionJob]:
        self._calls.append(("get_jobs", db, id, ctx, limit))
        return await self._sync_lifecycle.get_jobs(db, id=id, ctx=ctx, limit=limit)

    async def cancel_job(
        self,
        db: AsyncSession,
        *,
        source_connection_id: UUID,
        job_id: UUID,
        ctx: ApiContext,
    ) -> SourceConnectionJob:
        self._calls.append(("cancel_job", db, source_connection_id, job_id, ctx))
        return await self._sync_lifecycle.cancel_job(
            db, source_connection_id=source_connection_id, job_id=job_id, ctx=ctx
        )
