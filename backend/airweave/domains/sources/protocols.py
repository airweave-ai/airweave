"""Protocols for source services."""

from typing import Protocol

from airweave import schemas
from airweave.core.protocols.registry import RegistryProtocol
from airweave.domains.sources.types import SourceRegistryEntry


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
