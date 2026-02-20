"""Protocols for source services."""

from typing import Any, Dict, Optional, Protocol, Union
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.protocols.registry import RegistryProtocol
from airweave.domains.sources.types import SourceRegistryEntry
from airweave.platform.sources._base import BaseSource


class SourceServiceProtocol(Protocol):
    """Protocol for source services."""

    async def get(self, short_name: str) -> schemas.Source:
        """Get a source by short name."""
        ...

    async def list(self) -> list[schemas.Source]:
        """List all sources."""
        ...


class SourceRegistryProtocol(RegistryProtocol[SourceRegistryEntry], Protocol):
    """Source registry protocol."""

    pass


class SourceLifecycleServiceProtocol(Protocol):
    """Manages source instance creation, configuration, and validation.

    Replaces scattered resource_locator.get_source() + manual
    .create()/.validate()/set_*() calls across source connections, sync,
    and search.
    """

    async def create(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        ctx: ApiContext,
        *,
        access_token: Optional[str] = None,
    ) -> BaseSource:
        """Create a fully configured source instance for sync or search.

        Loads the source connection, resolves the source class from the
        registry, decrypts credentials, creates the instance, and configures:
        - Contextual logger
        - Token manager (OAuth sources with refresh)
        - HTTP client (vanilla httpx or Pipedream proxy)
        - Rate limiting wrapper (AirweaveHttpClient)
        - Sync identifiers

        Args:
            db: Database session
            source_connection_id: The source connection to build from
            ctx: API context (provides org, logger)
            access_token: Direct token injection (skips credential loading
                          and token manager)

        Returns:
            Fully configured BaseSource instance.
        """
        ...

    async def validate(
        self,
        short_name: str,
        credentials: Union[dict, BaseModel, str],
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Validate credentials by creating a lightweight source and
        calling .validate().

        No token manager, no HTTP wrapping, no rate limiting.
        Used during source connection creation to verify credentials
        before persisting.

        Args:
            short_name: Source short name (e.g., "github", "slack")
            credentials: Auth credentials (dict, string token, or
                         Pydantic config object)
            config: Optional source-specific config

        Raises:
            SourceNotFoundError: If source short_name is not in the registry.
            SourceCreationError: If source_class.create() fails.
            SourceValidationError: If source.validate() returns False or raises.
        """
        ...
