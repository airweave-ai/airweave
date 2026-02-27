"""Integration credential repository wrapping crud.integration_credential."""

from typing import Optional, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.credentials.protocols import (
    IntegrationCredentialRepositoryProtocol,
)
from airweave.models.integration_credential import IntegrationCredential
from airweave.schemas.integration_credential import (
    IntegrationCredentialCreateEncrypted,
    IntegrationCredentialUpdate,
)


class IntegrationCredentialRepository(IntegrationCredentialRepositoryProtocol):
    """Delegates to the crud.integration_credential singleton."""

    async def get(
        self, db: AsyncSession, id: UUID, ctx: ApiContext
    ) -> Optional[IntegrationCredential]:
        return await crud.integration_credential.get(db, id, ctx)

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: IntegrationCredential,
        obj_in: Union[IntegrationCredentialUpdate, dict],
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> IntegrationCredential:
        return await crud.integration_credential.update(
            db, db_obj=db_obj, obj_in=obj_in, ctx=ctx, uow=uow
        )

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: IntegrationCredentialCreateEncrypted,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> IntegrationCredential:
        return await crud.integration_credential.create(db, obj_in=obj_in, ctx=ctx, uow=uow)
