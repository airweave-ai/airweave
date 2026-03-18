"""Test that EmbedQuery passes purpose=QUERY to the dense embedder."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from airweave.domains.embedders.protocols import EmbeddingPurpose
from airweave.schemas.search import RetrievalStrategy
from airweave.search.operations.embed_query import EmbedQuery


@pytest.mark.asyncio
async def test_embed_query_passes_query_purpose():
    """EmbedQuery must pass purpose=QUERY so Gemini uses RETRIEVAL_QUERY task type."""
    dense_embedder = MagicMock()
    dense_result = MagicMock()
    dense_result.vector = [0.1] * 768
    dense_embedder.embed_many = AsyncMock(return_value=[dense_result])
    dense_embedder.embed = AsyncMock(return_value=dense_result)
    dense_embedder.dimensions = 768

    sparse_embedder = MagicMock()
    sparse_result = MagicMock()
    sparse_embedder.embed_many = AsyncMock(return_value=[sparse_result])
    sparse_embedder.embed = AsyncMock(return_value=sparse_result)

    op = EmbedQuery(
        strategy=RetrievalStrategy.HYBRID,
        dense_embedder=dense_embedder,
        sparse_embedder=sparse_embedder,
    )

    # Build minimal context and state
    context = MagicMock()
    context.query = "test search query"
    context.emitter = MagicMock()
    context.emitter.emit = AsyncMock()
    state = MagicMock()
    state.expanded_queries = []

    ctx = MagicMock()
    ctx.logger = MagicMock()

    await op.execute(context, state, ctx)

    # Verify purpose=QUERY was passed to dense embedder
    call_kwargs = dense_embedder.embed_many.call_args
    assert call_kwargs.kwargs.get("purpose") == EmbeddingPurpose.QUERY
