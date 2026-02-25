"""Fake connection repository for testing."""

from typing import Optional, Union
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core.shared_models import IntegrationType
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.connection import Connection
from airweave.schemas.connection import ConnectionCreate, ConnectionUpdate


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

    async def get_s3_destination_for_org(
        self, db: AsyncSession, ctx: ApiContext
    ) -> Optional[Connection]:
        self._calls.append(("get_s3_destination_for_org", db, ctx))
        for connection in self._store.values():
            if (
                connection.organization_id == ctx.organization.id
                and connection.short_name == "s3"
                and str(connection.integration_type).upper().endswith("DESTINATION")
            ):
                return connection
        return None

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: ConnectionCreate,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> Connection:
        self._calls.append(("create", db, obj_in, ctx, uow))
        connection = Connection(
            id=uuid4(),
            organization_id=ctx.organization.id,
            name=obj_in.name,
            readable_id=obj_in.readable_id,
            description=obj_in.description,
            integration_type=obj_in.integration_type,
            integration_credential_id=obj_in.integration_credential_id,
            status=obj_in.status,
            short_name=obj_in.short_name,
        )
        self._store[connection.id] = connection
        if connection.readable_id:
            self._readable_store[connection.readable_id] = connection
        return connection

    async def get_by_integration_type(
        self, db: AsyncSession, *, integration_type: IntegrationType, ctx: ApiContext
    ) -> list[Connection]:
        self._calls.append(("get_by_integration_type", db, integration_type, ctx))
        return [
            conn
            for conn in self._store.values()
            if conn.integration_type == integration_type
            and conn.organization_id == ctx.organization.id
        ]

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: Connection,
        obj_in: Union[ConnectionUpdate, dict],
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> Connection:
        self._calls.append(("update", db, db_obj, obj_in, ctx, uow))
        updates = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        for key, value in updates.items():
            setattr(db_obj, key, value)
        self._store[db_obj.id] = db_obj
        if db_obj.readable_id:
            self._readable_store[db_obj.readable_id] = db_obj
        return db_obj

    async def remove(self, db: AsyncSession, *, id: UUID, ctx: ApiContext) -> Optional[Connection]:
        self._calls.append(("remove", db, id, ctx))
        connection = self._store.pop(id, None)
        if connection and connection.readable_id in self._readable_store:
            self._readable_store.pop(connection.readable_id, None)
        return connection
