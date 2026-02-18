"""Repository implementations for OAuth2 domain, wrapping crud singletons."""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api.context import ApiContext
from airweave.domains.oauth.protocols import (
    OAuthConnectionRepositoryProtocol,
    OAuthCredentialRepositoryProtocol,
    OAuthSourceRepositoryProtocol,
)


class OAuthConnectionRepository(OAuthConnectionRepositoryProtocol):
    """Delegates to crud.connection."""

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Any:
        return await crud.connection.get(db, id, ctx)

    async def create(self, db: AsyncSession, *, obj_in: Any, ctx: ApiContext, uow: Any) -> Any:
        return await crud.connection.create(db, obj_in=obj_in, ctx=ctx, uow=uow)


class OAuthCredentialRepository(OAuthCredentialRepositoryProtocol):
    """Delegates to crud.integration_credential."""

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Any:
        return await crud.integration_credential.get(db, id, ctx)

    async def update(self, db: AsyncSession, *, db_obj: Any, obj_in: Any, ctx: ApiContext) -> Any:
        return await crud.integration_credential.update(
            db=db, db_obj=db_obj, obj_in=obj_in, ctx=ctx
        )

    async def create(self, db: AsyncSession, *, obj_in: Any, ctx: ApiContext, uow: Any) -> Any:
        return await crud.integration_credential.create(db, obj_in=obj_in, ctx=ctx, uow=uow)


class OAuthSourceRepository(OAuthSourceRepositoryProtocol):
    """Delegates to crud.source for config_class lookups."""

    async def get_by_short_name(self, db: AsyncSession, short_name: str) -> Any:
        return await crud.source.get_by_short_name(db, short_name)
