"""Fake connection repository for testing."""

from datetime import datetime, timezone
from typing import Optional, Union
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.connection import Connection
from airweave.schemas.connection import ConnectionCreate


class FakeConnectionRepository:
    """In-memory fake for ConnectionRepositoryProtocol."""

    def __init__(self) -> None:
        self._store: dict[UUID, Connection] = {}
        self._readable_store: dict[str, Connection] = {}
        self._calls: list[tuple] = []

    def seed(self, id: UUID, obj: Connection) -> None:
        self._store[id] = obj

    def seed_readable(self, readable_id: str, obj: Connection) -> None:
        self._readable_store[readable_id] = obj

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[Connection]:
        self._calls.append(("get", db, id, ctx))
        return self._store.get(id)

    async def get_by_readable_id(
        self, db: AsyncSession, readable_id: str, ctx: ApiContext
    ) -> Optional[Connection]:
        self._calls.append(("get_by_readable_id", db, readable_id, ctx))
        return self._readable_store.get(readable_id)

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: Union[ConnectionCreate, dict],
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> Connection:
        self._calls.append(("create", obj_in))
        data = obj_in.model_dump() if hasattr(obj_in, "model_dump") else dict(obj_in)
        now = datetime.now(timezone.utc)
        obj = Connection(**data)
        if not obj.id:
            obj.id = uuid4()
        if not obj.created_at:
            obj.created_at = now
        if not obj.modified_at:
            obj.modified_at = now
        if not obj.organization_id and ctx:
            obj.organization_id = ctx.organization.id
        self._store[obj.id] = obj
        return obj
