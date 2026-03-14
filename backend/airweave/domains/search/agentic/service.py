"""Agentic search service.

Full agent loop with tool calling.
Placeholder: returns empty SearchResults / publishes done event.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core.protocols.llm import LLMProtocol
from airweave.core.protocols.reranker import RerankerProtocol
from airweave.core.protocols.tokenizer import TokenizerProtocol
from airweave.domains.embedders.protocols import DenseEmbedderProtocol, SparseEmbedderProtocol
from airweave.domains.search.protocols import (
    AgenticSearchServiceProtocol,
    CollectionMetadataBuilderProtocol,
)
from airweave.domains.search.types import SearchResults

if TYPE_CHECKING:
    from airweave.core.protocols import PubSub
    from airweave.schemas.search_v2 import AgenticSearchRequest


class AgenticSearchService(AgenticSearchServiceProtocol):
    """Agentic search — full agent loop with tool calling.

    Placeholder: returns empty SearchResults / publishes done event.
    """

    def __init__(
        self,
        llm: LLMProtocol,
        tokenizer: TokenizerProtocol,
        reranker: Optional[RerankerProtocol],
        dense_embedder: DenseEmbedderProtocol,
        sparse_embedder: SparseEmbedderProtocol,
        metadata_builder: CollectionMetadataBuilderProtocol,
    ) -> None:
        """Initialize with LLM, tokenizer, reranker, embedders, and metadata builder."""
        self._llm = llm
        self._tokenizer = tokenizer
        self._reranker = reranker
        self._dense_embedder = dense_embedder
        self._sparse_embedder = sparse_embedder
        self._metadata_builder = metadata_builder

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
        pubsub: PubSub,
        request_id: str,
    ) -> None:
        """Placeholder: publishes a done event immediately."""
        await pubsub.publish(
            "agentic_search_v2",
            request_id,
            json.dumps({"type": "done", "results": []}),
        )
