"""Instant search service.

Embed query, fire at Vespa, return results.
Placeholder: returns empty SearchResults.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.domains.embedders.protocols import DenseEmbedderProtocol, SparseEmbedderProtocol
from airweave.domains.search.protocols import InstantSearchServiceProtocol
from airweave.domains.search.types import SearchResults

if TYPE_CHECKING:
    from airweave.schemas.search_v2 import InstantSearchRequest


class InstantSearchService(InstantSearchServiceProtocol):
    """Instant search — embed query, fire at Vespa, return results.

    Placeholder: returns empty SearchResults.
    """

    def __init__(
        self,
        dense_embedder: DenseEmbedderProtocol,
        sparse_embedder: SparseEmbedderProtocol,
    ) -> None:
        """Initialize with dense and sparse embedders."""
        self._dense_embedder = dense_embedder
        self._sparse_embedder = sparse_embedder

    async def search(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        readable_id: str,
        request: InstantSearchRequest,
    ) -> SearchResults:
        """Placeholder: returns empty results."""
        return SearchResults(results=[])
