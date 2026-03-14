"""Classic search service.

LLM generates a search plan, execute against Vespa, rerank results.
Placeholder: returns empty SearchResults.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core.protocols.llm import LLMProtocol
from airweave.core.protocols.reranker import RerankerProtocol
from airweave.core.protocols.tokenizer import TokenizerProtocol
from airweave.domains.embedders.protocols import DenseEmbedderProtocol, SparseEmbedderProtocol
from airweave.domains.search.protocols import (
    ClassicSearchServiceProtocol,
    CollectionMetadataBuilderProtocol,
)
from airweave.domains.search.types import SearchResults

if TYPE_CHECKING:
    from airweave.schemas.search_v2 import ClassicSearchRequest


class ClassicSearchService(ClassicSearchServiceProtocol):
    """Classic search — LLM generates search plan, execute against Vespa.

    Placeholder: returns empty SearchResults.
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
        request: ClassicSearchRequest,
    ) -> SearchResults:
        """Placeholder: returns empty results."""
        return SearchResults(results=[])
