"""Search domain service protocols."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.domains.search.types import (
    CollectionMetadata,
    FilterGroup,
    SearchPlan,
    SearchResults,
)

if TYPE_CHECKING:
    from airweave.schemas.search_v2 import (
        AgenticSearchRequest,
        ClassicSearchRequest,
        InstantSearchRequest,
    )


@runtime_checkable
class SearchPlanExecutorProtocol(Protocol):
    """Executes a search plan against the vector database.

    Shared pipeline: merge filters -> embed -> compile -> execute.
    Used by all three tiers (instant, classic, agentic).
    """

    async def execute(
        self,
        plan: SearchPlan,
        user_filter: list[FilterGroup],
        collection_id: str,
    ) -> SearchResults:
        """Execute a search plan and return results."""
        ...


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
    ) -> None:
        """Execute agentic search, emitting events to EventBus.

        The agent publishes domain events (thinking, tool_called, completed,
        failed) to the EventBus. The SearchStreamRelay subscriber bridges
        them to PubSub for SSE streaming.
        """
        ...
