"""Agentic search service.

Thin composition point — constructs the Agent and delegates.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core.protocols.event_bus import EventBus
from airweave.core.protocols.llm import LLMProtocol
from airweave.core.protocols.reranker import RerankerProtocol
from airweave.core.protocols.tokenizer import TokenizerProtocol
from airweave.domains.collections.protocols import CollectionRepositoryProtocol
from airweave.domains.search.adapters.vector_db.protocol import VectorDBProtocol
from airweave.domains.search.agentic.agent import Agent
from airweave.domains.search.config import SearchConfig
from airweave.domains.search.protocols import (
    AgenticSearchServiceProtocol,
    CollectionMetadataBuilderProtocol,
    SearchPlanExecutorProtocol,
)
from airweave.domains.search.types import SearchResults

if TYPE_CHECKING:
    from airweave.schemas.search_v2 import AgenticSearchRequest


class AgenticSearchService(AgenticSearchServiceProtocol):
    """Agentic search — constructs an Agent per request and delegates."""

    def __init__(
        self,
        llm: LLMProtocol,
        tokenizer: TokenizerProtocol,
        reranker: Optional[RerankerProtocol],
        executor: SearchPlanExecutorProtocol,
        vector_db: VectorDBProtocol,
        metadata_builder: CollectionMetadataBuilderProtocol,
        collection_repo: CollectionRepositoryProtocol,
        event_bus: EventBus,
    ) -> None:
        """Initialize with all dependencies needed to construct agents."""
        self._llm = llm
        self._tokenizer = tokenizer
        self._reranker = reranker
        self._executor = executor
        self._vector_db = vector_db
        self._metadata_builder = metadata_builder
        self._collection_repo = collection_repo
        self._event_bus = event_bus

    async def search(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        readable_id: str,
        request: AgenticSearchRequest,
    ) -> SearchResults:
        """Run agentic search and return results."""
        agent = Agent(
            llm=self._llm,
            tokenizer=self._tokenizer,
            reranker=self._reranker,
            executor=self._executor,
            vector_db=self._vector_db,
            metadata_builder=self._metadata_builder,
            collection_repo=self._collection_repo,
            event_bus=self._event_bus,
            config=SearchConfig(),
        )
        return await agent.run(db, ctx, readable_id, request)

    async def search_stream(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        readable_id: str,
        request: AgenticSearchRequest,
    ) -> None:
        """Run agentic search with event streaming.

        Same loop as search(). Events flow through event bus →
        stream relay → PubSub → SSE. The return value is discarded.
        """
        await self.search(db, ctx, readable_id, request)
