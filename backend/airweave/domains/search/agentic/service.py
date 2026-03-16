"""Agentic search service.

Full agent loop with tool calling.
Placeholder: returns empty SearchResults / publishes completed event via EventBus.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core.events.search import CompletedDiagnostics, SearchCompletedEvent
from airweave.core.protocols.event_bus import EventBus
from airweave.core.protocols.llm import LLMProtocol
from airweave.core.protocols.reranker import RerankerProtocol
from airweave.core.protocols.tokenizer import TokenizerProtocol
from airweave.domains.embedders.protocols import DenseEmbedderProtocol, SparseEmbedderProtocol
from airweave.domains.search.protocols import (
    AgenticSearchServiceProtocol,
    CollectionMetadataBuilderProtocol,
)
from airweave.domains.search.types import SearchResults
from airweave.schemas.search_v2 import SearchTier

if TYPE_CHECKING:
    from airweave.schemas.search_v2 import AgenticSearchRequest


class AgenticSearchService(AgenticSearchServiceProtocol):
    """Agentic search — full agent loop with tool calling.

    Placeholder: returns empty SearchResults / publishes completed event.
    """

    def __init__(
        self,
        llm: LLMProtocol,
        tokenizer: TokenizerProtocol,
        reranker: Optional[RerankerProtocol],
        dense_embedder: DenseEmbedderProtocol,
        sparse_embedder: SparseEmbedderProtocol,
        metadata_builder: CollectionMetadataBuilderProtocol,
        event_bus: EventBus,
    ) -> None:
        """Initialize with LLM, tokenizer, reranker, embedders, metadata builder, and event bus."""
        self._llm = llm
        self._tokenizer = tokenizer
        self._reranker = reranker
        self._dense_embedder = dense_embedder
        self._sparse_embedder = sparse_embedder
        self._metadata_builder = metadata_builder
        self._event_bus = event_bus

    async def search(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        readable_id: str,
        request: AgenticSearchRequest,
    ) -> SearchResults:
        """Placeholder: returns empty results."""
        return SearchResults(results=[])

    async def search_stream(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        readable_id: str,
        request: AgenticSearchRequest,
    ) -> None:
        """Placeholder: publishes a completed event immediately."""
        await self._event_bus.publish(
            SearchCompletedEvent(
                organization_id=ctx.organization.id,
                request_id=ctx.request_id,
                tier=SearchTier.AGENTIC,
                results=[],
                duration_ms=0,
                diagnostics=CompletedDiagnostics(),
            )
        )
