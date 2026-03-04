"""Unit tests for LocalDenseEmbedder.

All HTTP interactions are mocked — no network calls.
"""

from unittest.mock import AsyncMock

import httpx
import pytest

from airweave.domains.embedders.exceptions import (
    EmbedderConnectionError,
    EmbedderDimensionError,
    EmbedderInputError,
    EmbedderProviderError,
    EmbedderResponseError,
    EmbedderTimeoutError,
)
from airweave.domains.embedders.dense.local import LocalDenseEmbedder
from airweave.domains.embedders.types import DenseEmbedding

_DIMS = 384
_URL = "http://localhost:8080"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _vector(dims: int = _DIMS, val: float = 0.1) -> list[float]:
    """Create a dummy vector of the given dimensions."""
    return [val] * dims


def _build_embedder(client_mock: AsyncMock | None = None) -> LocalDenseEmbedder:
    """Build a LocalDenseEmbedder with mocked httpx client."""
    embedder = LocalDenseEmbedder(inference_url=_URL, dimensions=_DIMS)
    if client_mock is not None:
        embedder._client = client_mock
    return embedder


def _make_httpx_response(
    vector: list[float] | None = None,
    json_data: dict | None = None,
    status_code: int = 200,
) -> httpx.Response:
    """Create a fake httpx.Response."""
    if json_data is None:
        json_data = {"vector": vector if vector is not None else _vector()}
    import json

    return httpx.Response(
        status_code=status_code,
        content=json.dumps(json_data).encode(),
        headers={"content-type": "application/json"},
        request=httpx.Request("POST", f"{_URL}/vectors"),
    )


# ===========================================================================
# embed() — single text
# ===========================================================================


@pytest.mark.asyncio
async def test_embed_returns_single_dense_embedding():
    """embed() delegates to embed_many and returns the first result."""
    client = AsyncMock()
    client.post.return_value = _make_httpx_response()

    embedder = _build_embedder(client_mock=client)
    result = await embedder.embed("hello world")

    assert isinstance(result, DenseEmbedding)
    assert len(result.vector) == _DIMS


# ===========================================================================
# embed_many() — basic batching
# ===========================================================================


@pytest.mark.asyncio
async def test_embed_many_empty_returns_empty():
    """Empty input returns empty list without HTTP call."""
    client = AsyncMock()
    embedder = _build_embedder(client_mock=client)

    result = await embedder.embed_many([])

    assert result == []
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_embed_many_small_batch():
    """Small batch -> one HTTP call per text."""
    texts = [f"text {i}" for i in range(5)]
    client = AsyncMock()
    client.post.return_value = _make_httpx_response()

    embedder = _build_embedder(client_mock=client)
    result = await embedder.embed_many(texts)

    assert len(result) == 5
    assert all(isinstance(r, DenseEmbedding) for r in result)
    assert client.post.await_count == 5


@pytest.mark.asyncio
async def test_embed_many_sub_batching():
    """More than 64 texts -> split into multiple sub-batches."""
    texts = [f"text {i}" for i in range(100)]
    client = AsyncMock()
    client.post.return_value = _make_httpx_response()

    embedder = _build_embedder(client_mock=client)
    result = await embedder.embed_many(texts)

    assert len(result) == 100
    assert client.post.await_count == 100


# ===========================================================================
# Input validation
# ===========================================================================


@pytest.mark.asyncio
async def test_blank_text_raises_input_error():
    """Blank/whitespace-only text raises EmbedderInputError."""
    embedder = _build_embedder()

    with pytest.raises(EmbedderInputError, match="empty or blank"):
        await embedder.embed_many(["valid", "   "])


@pytest.mark.asyncio
async def test_empty_string_raises_input_error():
    """Empty string raises EmbedderInputError."""
    embedder = _build_embedder()

    with pytest.raises(EmbedderInputError, match="empty or blank"):
        await embedder.embed("")


# ===========================================================================
# Error translation
# ===========================================================================


@pytest.mark.asyncio
async def test_http_status_error_raises_provider_error():
    """HTTP status error raises EmbedderProviderError."""
    client = AsyncMock()
    response = _make_httpx_response(json_data={"error": "bad"}, status_code=500)
    client.post.side_effect = httpx.HTTPStatusError(
        message="Server Error",
        request=httpx.Request("POST", f"{_URL}/vectors"),
        response=response,
    )

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(EmbedderProviderError, match="status 500"):
        await embedder.embed("test")


@pytest.mark.asyncio
async def test_connect_error_raises_connection_error():
    """Connection error raises EmbedderConnectionError."""
    client = AsyncMock()
    client.post.side_effect = httpx.ConnectError("connection refused")

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(EmbedderConnectionError, match="connection failed"):
        await embedder.embed("test")


@pytest.mark.asyncio
async def test_timeout_raises_timeout_error():
    """Timeout raises EmbedderTimeoutError."""
    client = AsyncMock()
    client.post.side_effect = httpx.ReadTimeout("timed out")

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(EmbedderTimeoutError, match="timed out"):
        await embedder.embed("test")


@pytest.mark.asyncio
async def test_request_error_raises_connection_error():
    """Other httpx.RequestError raises EmbedderConnectionError."""
    client = AsyncMock()
    client.post.side_effect = httpx.RequestError("something failed")

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(EmbedderConnectionError, match="connection failed"):
        await embedder.embed("test")


@pytest.mark.asyncio
async def test_missing_vector_key_raises_response_error():
    """Missing 'vector' key in response raises EmbedderResponseError."""
    client = AsyncMock()
    client.post.return_value = _make_httpx_response(json_data={"embedding": [0.1] * _DIMS})

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(EmbedderResponseError, match="missing 'vector' key"):
        await embedder.embed("test")


@pytest.mark.asyncio
async def test_dimension_mismatch_raises_dimension_error():
    """Wrong vector dimensions raises EmbedderDimensionError."""
    wrong_dims = _DIMS + 10
    client = AsyncMock()
    client.post.return_value = _make_httpx_response(vector=[0.1] * wrong_dims)

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(EmbedderDimensionError) as exc_info:
        await embedder.embed("test")

    assert exc_info.value.expected == _DIMS
    assert exc_info.value.actual == wrong_dims


@pytest.mark.asyncio
async def test_error_chaining_preserves_original():
    """Translated errors chain the original exception via __cause__."""
    client = AsyncMock()
    original = httpx.ConnectError("connection refused")
    client.post.side_effect = original

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(EmbedderConnectionError) as exc_info:
        await embedder.embed("test")

    assert exc_info.value.__cause__ is original


# ===========================================================================
# close()
# ===========================================================================


@pytest.mark.asyncio
async def test_close_calls_client_aclose():
    """close() delegates to the underlying httpx.AsyncClient."""
    client = AsyncMock()
    embedder = _build_embedder(client_mock=client)

    await embedder.close()

    client.aclose.assert_awaited_once()
