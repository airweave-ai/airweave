"""Protocols for integration credential repository and service."""

from typing import Any, Optional, Protocol, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.credentials.types import DecryptedCredential
from airweave.models.integration_credential import IntegrationCredential
from airweave.schemas.integration_credential import (
    IntegrationCredentialCreateEncrypted,
    IntegrationCredentialUpdate,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


class IntegrationCredentialRepositoryProtocol(Protocol):
    """Access to integration credential records."""

    async def get(
        self, db: AsyncSession, id: UUID, ctx: ApiContext
    ) -> IntegrationCredential:
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


class IntegrationCredentialServiceProtocol(Protocol):
    """Business-logic layer for integration credentials.

    Provides get (decrypt), create (encrypt), and update operations
    so callers never touch raw encrypted blobs or the CredentialEncryptor
    directly.
    """

    async def get(
        self,
        db: AsyncSession,
        credential_id: UUID,
        ctx: ApiContext,
    ) -> DecryptedCredential:
        """Get and decrypt a credential record.

        Raises NotFoundException if the credential does not exist.
        """
        ...

    async def create(
        self,
        db: AsyncSession,
        *,
        short_name: str,
        source_name: str,
        auth_payload: dict[str, Any],
        auth_method: AuthenticationMethod,
        oauth_type: Optional[OAuthType],
        auth_config_name: Optional[str],
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> IntegrationCredential:
        """Encrypt and persist a new credential record."""
        ...

    async def update(
        self,
        db: AsyncSession,
        credential: DecryptedCredential,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> IntegrationCredential:
        """Re-encrypt and persist an updated DecryptedCredential."""
        ...
