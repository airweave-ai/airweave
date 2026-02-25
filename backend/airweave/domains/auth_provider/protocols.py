from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.protocols.registry import RegistryProtocol
from airweave.domains.auth_provider.types import AuthProviderRegistryEntry


class AuthProviderRegistryProtocol(RegistryProtocol[AuthProviderRegistryEntry], Protocol):
    """Auth provider registry protocol."""

    pass


class AuthProviderServiceProtocol(Protocol):
    """Service for auth provider connection operations."""

    async def list_connections(
        self, db: AsyncSession, *, ctx: ApiContext, skip: int = 0, limit: int = 100
    ) -> list[schemas.AuthProviderConnection]:
        """List auth provider connections for the current organization."""
        ...

    async def get_connection(
        self, db: AsyncSession, *, readable_id: str, ctx: ApiContext
    ) -> schemas.AuthProviderConnection:
        """Get an auth provider connection."""
        ...

    async def create_connection(
        self,
        db: AsyncSession,
        *,
        obj_in: schemas.AuthProviderConnectionCreate,
        ctx: ApiContext,
    ) -> schemas.AuthProviderConnection:
        """Create an auth provider connection."""
        ...

    async def update_connection(
        self,
        db: AsyncSession,
        *,
        readable_id: str,
        obj_in: schemas.AuthProviderConnectionUpdate,
        ctx: ApiContext,
    ) -> schemas.AuthProviderConnection:
        """Update an auth provider connection."""
        ...

    async def delete_connection(
        self, db: AsyncSession, *, readable_id: str, ctx: ApiContext
    ) -> schemas.AuthProviderConnection:
        """Delete an auth provider connection."""
        ...
