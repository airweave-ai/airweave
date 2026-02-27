"""Fake integration credential repository for testing."""

from typing import Optional, Union
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.integration_credential import IntegrationCredential
from airweave.schemas.integration_credential import (
    IntegrationCredentialCreateEncrypted,
    IntegrationCredentialUpdate,
)


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

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: IntegrationCredentialCreateEncrypted,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> IntegrationCredential:
        self._calls.append(("create", db, obj_in, ctx, uow))
        credential = IntegrationCredential(
            id=uuid4(),
            organization_id=ctx.organization.id,
            name=obj_in.name,
            integration_short_name=obj_in.integration_short_name,
            description=obj_in.description,
            integration_type=obj_in.integration_type,
            authentication_method=obj_in.authentication_method,
            oauth_type=obj_in.oauth_type,
            auth_config_class=obj_in.auth_config_class,
            encrypted_credentials=obj_in.encrypted_credentials,
        )
        self._store[credential.id] = credential
        return credential
