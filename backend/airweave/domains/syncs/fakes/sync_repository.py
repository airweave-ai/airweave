"""Fake sync repository for testing."""

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.sync import Sync
from airweave.schemas.sync import SyncCreate, SyncUpdate


class FakeSyncRepository:
    """In-memory fake for SyncRepositoryProtocol."""

    def __init__(self) -> None:
        """Initialize with empty stores."""
        self._store: dict[UUID, schemas.Sync] = {}
        self._models: dict[UUID, Sync] = {}
        self._calls: list[tuple] = []
        self._create_result: Optional[schemas.Sync] = None

    def seed(self, id: UUID, sync_schema: schemas.Sync) -> None:
        """Seed a sync by ID (with-connections variant)."""
        self._store[id] = sync_schema

    def seed_model(self, id: UUID, sync_model: Sync) -> None:
        """Seed a raw Sync ORM model (without-connections variant)."""
        self._models[id] = sync_model

    def set_create_result(self, sync_schema: schemas.Sync) -> None:
        """Configure create() return value."""
        self._create_result = sync_schema

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[schemas.Sync]:
        """Return seeded sync schema or None."""
        self._calls.append(("get", db, id, ctx))
        return self._store.get(id)

    async def get_without_connections(
        self, db: AsyncSession, id: UUID, ctx: ApiContext
    ) -> Optional[Sync]:
        """Return seeded sync model or None."""
        self._calls.append(("get_without_connections", db, id, ctx))
        return self._models.get(id)

    async def create(
        self,
        db: AsyncSession,
        obj_in: SyncCreate,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> schemas.Sync:
        """Record call and return canned result."""
        self._calls.append(("create", db, obj_in, ctx, uow))
        if self._create_result is None:
            raise RuntimeError("FakeSyncRepository.create_result not configured")
        return self._create_result

    async def update(
        self,
        db: AsyncSession,
        db_obj: Sync,
        obj_in: SyncUpdate,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> Sync:
        """Record call and return db_obj with fields patched."""
        self._calls.append(("update", db, db_obj, obj_in, ctx, uow))
        for k, v in obj_in.model_dump(exclude_unset=True).items():
            setattr(db_obj, k, v)
        return db_obj
