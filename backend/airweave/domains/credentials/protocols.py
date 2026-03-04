"""Protocols for the credentials domain."""

from typing import Optional, Protocol, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.integration_credential import IntegrationCredential
from airweave.schemas.integration_credential import (
    IntegrationCredentialCreateEncrypted,
    IntegrationCredentialUpdate,
)


# ---------------------------------------------------------------------------
# Token refresh protocols
# ---------------------------------------------------------------------------


class CredentialRefresherProtocol(Protocol):
    """Strategy for obtaining a fresh access token.

    Implementations handle the HOW of refreshing (OAuth2 flow, auth provider
    delegation, etc.) and are responsible for persisting updated credentials.
    """

    async def refresh(self) -> str:
        """Fetch a fresh access token and persist updated credentials.

        Returns:
            The new access token string.

        Raises:
            TokenRefreshError: If the refresh attempt fails.
        """
        ...


class TokenRefresherProtocol(Protocol):
    """Stateful token lifecycle manager consumed by sources.

    Manages WHEN to refresh (timer, lock, proactive vs reactive) and
    delegates the actual refresh to a ``CredentialRefresherProtocol``.
    """

    async def get_valid_token(self) -> str:
        """Return a valid access token, refreshing proactively if stale."""
        ...

    async def refresh_on_unauthorized(self) -> str:
        """Force an immediate refresh after a 401 response."""
        ...


# ---------------------------------------------------------------------------
# Repository protocol
# ---------------------------------------------------------------------------


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

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: IntegrationCredentialCreateEncrypted,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> IntegrationCredential:
        """Create an integration credential."""
        ...
