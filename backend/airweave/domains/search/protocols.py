"""Search domain service protocols."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.domains.search.types import CollectionMetadata, SearchResults

if TYPE_CHECKING:
    from airweave.core.protocols import PubSub
    from airweave.schemas.search_v2 import (
        AgenticSearchRequest,
        ClassicSearchRequest,
        InstantSearchRequest,
    )


@runtime_checkable
class CollectionMetadataBuilderProtocol(Protocol):
    """Builds collection metadata from repository data."""

    async def build(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        collection_readable_id: str,
    ) -> CollectionMetadata:
        """Build metadata for a collection by readable ID."""
        ...


@runtime_checkable
class InstantSearchServiceProtocol(Protocol):
    """Instant search — embed query, fire at Vespa, return results."""

    async def search(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        readable_id: str,
        request: InstantSearchRequest,
    ) -> SearchResults:
        """Execute instant search and return results."""
        ...


@runtime_checkable
class ClassicSearchServiceProtocol(Protocol):
    """Classic search — LLM generates search plan, execute against Vespa."""

    async def search(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        readable_id: str,
        request: ClassicSearchRequest,
    ) -> SearchResults:
        """Execute classic search and return results."""
        ...


@runtime_checkable
class AgenticSearchServiceProtocol(Protocol):
    """Agentic search — full agent loop with tool calling."""

    async def search(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        readable_id: str,
        request: AgenticSearchRequest,
    ) -> SearchResults:
        """Execute agentic search and return results."""
        ...

    async def search_stream(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        readable_id: str,
        request: AgenticSearchRequest,
        pubsub: PubSub,
        request_id: str,
    ) -> None:
        """Execute agentic search and stream results via PubSub."""
        ...
