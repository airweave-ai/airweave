"""Fake integration credential repository for testing."""

from typing import Optional, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.integration_credential import IntegrationCredential
from airweave.schemas.integration_credential import IntegrationCredentialUpdate


class FakeIntegrationCredentialRepository:
    """In-memory fake for IntegrationCredentialRepositoryProtocol."""

    def __init__(self) -> None:
        self._store: dict[UUID, IntegrationCredential] = {}
        self._calls: list[tuple] = []

    def seed(self, id: UUID, obj: IntegrationCredential) -> None:
        self._store[id] = obj

    async def get(
        self, db: AsyncSession, id: UUID, ctx: ApiContext
    ) -> Optional[IntegrationCredential]:
        self._calls.append(("get", db, id, ctx))
        return self._store.get(id)

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: IntegrationCredential,
        obj_in: Union[IntegrationCredentialUpdate, dict],
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> IntegrationCredential:
        self._calls.append(("update", db, db_obj, obj_in, ctx, uow))
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        self._store[db_obj.id] = db_obj
        return db_obj
