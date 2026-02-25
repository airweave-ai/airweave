"""Protocols for integration credential repository."""

from typing import Optional, Protocol, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.integration_credential import IntegrationCredential
from airweave.schemas.integration_credential import IntegrationCredentialUpdate


class IntegrationCredentialRepositoryProtocol(Protocol):
    """Access to integration credential records."""

    async def get(
        self, db: AsyncSession, id: UUID, ctx: ApiContext
    ) -> Optional[IntegrationCredential]:
        """Get an integration credential by ID within an organization."""
        ...

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: IntegrationCredential,
        obj_in: Union[IntegrationCredentialUpdate, dict],
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> IntegrationCredential:
        """Update an integration credential."""
        ...
