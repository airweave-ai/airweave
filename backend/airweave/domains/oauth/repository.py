"""Repository implementations for OAuth domain, wrapping crud singletons."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api.context import ApiContext
from airweave.crud import connection_init_session, redirect_session
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.connection import Connection
from airweave.models.connection_init_session import ConnectionInitSession
from airweave.models.integration_credential import IntegrationCredential
from airweave.models.redirect_session import RedirectSession
from airweave.models.source import Source
from airweave.schemas.connection import ConnectionCreate
from airweave.schemas.integration_credential import (
    IntegrationCredentialCreateEncrypted,
    IntegrationCredentialUpdate,
)


class OAuthConnectionRepository:
    """Delegates to crud.connection."""

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Connection:
        return await crud.connection.get(db, id, ctx)

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: ConnectionCreate,
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> Connection:
        return await crud.connection.create(db, obj_in=obj_in, ctx=ctx, uow=uow)


class OAuthCredentialRepository:
    """Delegates to crud.integration_credential."""

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> IntegrationCredential:
        return await crud.integration_credential.get(db, id, ctx)

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: IntegrationCredential,
        obj_in: IntegrationCredentialUpdate,
        ctx: ApiContext,
    ) -> IntegrationCredential:
        return await crud.integration_credential.update(
            db=db, db_obj=db_obj, obj_in=obj_in, ctx=ctx
        )

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: IntegrationCredentialCreateEncrypted,
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> IntegrationCredential:
        return await crud.integration_credential.create(db, obj_in=obj_in, ctx=ctx, uow=uow)


class OAuthSourceRepository:
    """Delegates to crud.source for config_class lookups."""

    async def get_by_short_name(self, db: AsyncSession, short_name: str) -> Optional[Source]:
        return await crud.source.get_by_short_name(db, short_name)


class OAuthInitSessionRepository:
    """Delegates to crud.connection_init_session."""

    async def get_by_state_no_auth(
        self, db: AsyncSession, *, state: str
    ) -> Optional[ConnectionInitSession]:
        return await connection_init_session.get_by_state_no_auth(db, state=state)

    async def get_by_oauth_token_no_auth(
        self, db: AsyncSession, *, oauth_token: str
    ) -> Optional[ConnectionInitSession]:
        return await connection_init_session.get_by_oauth_token_no_auth(db, oauth_token=oauth_token)

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: Dict[str, Any],
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> ConnectionInitSession:
        return await connection_init_session.create(db, obj_in=obj_in, ctx=ctx, uow=uow)

    async def mark_completed(
        self,
        db: AsyncSession,
        *,
        session_id: UUID,
        final_connection_id: Optional[UUID],
        ctx: ApiContext,
    ) -> None:
        await connection_init_session.mark_completed(
            db, session_id=session_id, final_connection_id=final_connection_id, ctx=ctx
        )


class OAuthRedirectSessionRepository:
    """Delegates to crud.redirect_session."""

    async def generate_unique_code(self, db: AsyncSession, *, length: int) -> str:
        return await redirect_session.generate_unique_code(db, length=length)

    async def create(
        self,
        db: AsyncSession,
        *,
        code: str,
        final_url: str,
        expires_at: datetime,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> Any:
        return await redirect_session.create(
            db, code=code, final_url=final_url, expires_at=expires_at, ctx=ctx, uow=uow
        )

    async def get_by_code(self, db: AsyncSession, code: str) -> Optional[RedirectSession]:
        return await crud.redirect_session.get_by_code(db, code)
