"""Fake integration credential repository for testing."""

from typing import Optional, Union
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.integration_credential import IntegrationCredential
from airweave.schemas.integration_credential import IntegrationCredentialCreateEncrypted


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

    async def create_encrypted(
        self,
        db: AsyncSession,
        *,
        obj_in: Union[IntegrationCredentialCreateEncrypted, dict],
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> IntegrationCredential:
        self._calls.append(("create_encrypted", obj_in))
        data = obj_in.model_dump() if hasattr(obj_in, "model_dump") else dict(obj_in)
        obj = IntegrationCredential(**data)
        if not obj.id:
            obj.id = uuid4()
        self._store[obj.id] = obj
        return obj
