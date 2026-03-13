"""Unit tests for GeminiDenseEmbedder.

All Google GenAI SDK interactions are mocked — no network calls.
"""

import math
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.domains.embedders.dense.gemini import GeminiDenseEmbedder
from airweave.domains.embedders.exceptions import (
    EmbedderAuthError,
    EmbedderConnectionError,
    EmbedderDimensionError,
    EmbedderInputError,
    EmbedderProviderError,
    EmbedderRateLimitError,
    EmbedderResponseError,
    EmbedderTimeoutError,
)
from airweave.domains.embedders.protocols import EmbeddingPurpose
from airweave.domains.embedders.types import DenseEmbedding

_DIMS = 256
_MODEL = "gemini-embedding-2-preview"
_API_KEY = "test-gemini-key"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_embedding_object(vector: list[float]) -> SimpleNamespace:
    """Create a fake Gemini embedding response object."""
    return SimpleNamespace(values=vector)


def _make_response(vectors: list[list[float]]) -> SimpleNamespace:
    """Create a fake Gemini embed_content response."""
    embeddings = [_make_embedding_object(v) for v in vectors]
    return SimpleNamespace(embeddings=embeddings)


def _vector(dims: int = _DIMS, val: float = 0.1) -> list[float]:
    """Create a dummy vector of the given dimensions."""
    return [val] * dims


def _build_embedder(
    client_mock: MagicMock | None = None,
    dims: int = _DIMS,
) -> GeminiDenseEmbedder:
    """Build a GeminiDenseEmbedder with mocked dependencies."""
    with patch("airweave.domains.embedders.dense.gemini.genai") as mock_genai:
        if client_mock is None:
            client_mock = MagicMock()
            client_mock.aio.models.embed_content = AsyncMock()
            client_mock.aio.live._api_client._http_client.aclose = AsyncMock()
        mock_genai.Client.return_value = client_mock

        embedder = GeminiDenseEmbedder(
            api_key=_API_KEY,
            model=_MODEL,
            dimensions=dims,
        )
    return embedder


# ===========================================================================
# embed() — single text
# ===========================================================================


@pytest.mark.asyncio
async def test_embed_returns_single_dense_embedding():
    """embed() delegates to embed_many and returns the first result."""
    client = MagicMock()
    client.aio.models.embed_content = AsyncMock(return_value=_make_response([_vector()]))
    client.aio.live._api_client._http_client.aclose = AsyncMock()

    embedder = _build_embedder(client_mock=client)
    result = await embedder.embed("hello world")

    assert isinstance(result, DenseEmbedding)
    assert len(result.vector) == _DIMS
    client.aio.models.embed_content.assert_awaited_once()


# ===========================================================================
# embed_many() — basic batching
# ===========================================================================


@pytest.mark.asyncio
async def test_embed_many_empty_returns_empty():
    """Empty input returns empty list without API call."""
    client = MagicMock()
    client.aio.models.embed_content = AsyncMock()
    client.aio.live._api_client._http_client.aclose = AsyncMock()

    embedder = _build_embedder(client_mock=client)
    result = await embedder.embed_many([])

    assert result == []
    client.aio.models.embed_content.assert_not_awaited()


@pytest.mark.asyncio
async def test_embed_many_single_batch():
    """Fewer than 100 texts -> single API call."""
    texts = [f"text {i}" for i in range(5)]
    vectors = [_vector() for _ in texts]
    client = MagicMock()
    client.aio.models.embed_content = AsyncMock(return_value=_make_response(vectors))
    client.aio.live._api_client._http_client.aclose = AsyncMock()

    embedder = _build_embedder(client_mock=client)
    result = await embedder.embed_many(texts)

    assert len(result) == 5
    assert all(isinstance(r, DenseEmbedding) for r in result)
    client.aio.models.embed_content.assert_awaited_once()


@pytest.mark.asyncio
async def test_embed_many_sub_batching():
    """More than 100 texts -> split into multiple sub-batches."""
    texts = [f"text {i}" for i in range(150)]

    call_count = 0

    async def fake_embed(**kwargs):
        nonlocal call_count
        call_count += 1
        n = len(kwargs["contents"])
        return _make_response([_vector() for _ in range(n)])

    client = MagicMock()
    client.aio.models.embed_content = AsyncMock(side_effect=fake_embed)
    client.aio.live._api_client._http_client.aclose = AsyncMock()

    embedder = _build_embedder(client_mock=client)
    result = await embedder.embed_many(texts)

    assert len(result) == 150
    assert call_count == 2  # 100 + 50


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


@pytest.mark.asyncio
async def test_text_exceeding_char_limit_raises_input_error():
    """Text exceeding the character limit raises EmbedderInputError."""
    embedder = _build_embedder()
    # 40001 characters exceeds the 40000 limit
    long_text = "a" * 40_001

    with pytest.raises(EmbedderInputError, match="40001 characters.*exceeding the limit"):
        await embedder.embed(long_text)


# ===========================================================================
# Response validation
# ===========================================================================


@pytest.mark.asyncio
async def test_count_mismatch_raises_response_error():
    """Mismatched embedding count raises EmbedderResponseError."""
    client = MagicMock()
    # Send 3 texts but get 2 embeddings back
    client.aio.models.embed_content = AsyncMock(
        return_value=_make_response([_vector(), _vector()])
    )
    client.aio.live._api_client._http_client.aclose = AsyncMock()

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(EmbedderResponseError, match="Expected 3.*got 2"):
        await embedder.embed_many(["a", "b", "c"])


@pytest.mark.asyncio
async def test_dimension_mismatch_raises_dimension_error():
    """Wrong vector dimensions raises EmbedderDimensionError."""
    wrong_dims = _DIMS + 10
    client = MagicMock()
    client.aio.models.embed_content = AsyncMock(
        return_value=_make_response([[0.1] * wrong_dims])
    )
    client.aio.live._api_client._http_client.aclose = AsyncMock()

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(EmbedderDimensionError) as exc_info:
        await embedder.embed("hello")

    assert exc_info.value.expected == _DIMS
    assert exc_info.value.actual == wrong_dims


# ===========================================================================
# L2 normalization
# ===========================================================================


@pytest.mark.asyncio
async def test_l2_normalization_for_sub_native_dims():
    """Sub-3072 dimensions triggers L2 normalization."""
    raw_vector = [3.0, 4.0]  # norm = 5.0
    expected = [3.0 / 5.0, 4.0 / 5.0]

    client = MagicMock()
    client.aio.models.embed_content = AsyncMock(return_value=_make_response([raw_vector]))
    client.aio.live._api_client._http_client.aclose = AsyncMock()

    embedder = _build_embedder(client_mock=client, dims=2)
    result = await embedder.embed("test")

    assert len(result.vector) == 2
    assert abs(result.vector[0] - expected[0]) < 1e-6
    assert abs(result.vector[1] - expected[1]) < 1e-6

    # Verify unit length
    norm = math.sqrt(sum(x * x for x in result.vector))
    assert abs(norm - 1.0) < 1e-6


@pytest.mark.asyncio
async def test_no_normalization_at_native_dims():
    """At 3072 (native) dimensions, no normalization is applied."""
    raw_vector = [0.5] * 3072

    client = MagicMock()
    client.aio.models.embed_content = AsyncMock(return_value=_make_response([raw_vector]))
    client.aio.live._api_client._http_client.aclose = AsyncMock()

    embedder = _build_embedder(client_mock=client, dims=3072)
    result = await embedder.embed("test")

    # Should be the raw vector, not normalized
    assert result.vector == raw_vector


# ===========================================================================
# Purpose -> task type mapping
# ===========================================================================


@pytest.mark.asyncio
async def test_document_purpose_maps_to_retrieval_document():
    """DOCUMENT purpose passes RETRIEVAL_DOCUMENT task type."""
    client = MagicMock()
    client.aio.models.embed_content = AsyncMock(return_value=_make_response([_vector()]))
    client.aio.live._api_client._http_client.aclose = AsyncMock()

    embedder = _build_embedder(client_mock=client)
    await embedder.embed("test", purpose=EmbeddingPurpose.DOCUMENT)

    call_kwargs = client.aio.models.embed_content.call_args
    config = call_kwargs.kwargs["config"]
    assert config["task_type"] == "RETRIEVAL_DOCUMENT"


@pytest.mark.asyncio
async def test_query_purpose_maps_to_retrieval_query():
    """QUERY purpose passes RETRIEVAL_QUERY task type."""
    client = MagicMock()
    client.aio.models.embed_content = AsyncMock(return_value=_make_response([_vector()]))
    client.aio.live._api_client._http_client.aclose = AsyncMock()

    embedder = _build_embedder(client_mock=client)
    await embedder.embed("search query", purpose=EmbeddingPurpose.QUERY)

    call_kwargs = client.aio.models.embed_content.call_args
    config = call_kwargs.kwargs["config"]
    assert config["task_type"] == "RETRIEVAL_QUERY"


# ===========================================================================
# Error translation
# ===========================================================================


@pytest.mark.asyncio
async def test_client_error_401_raises_auth_error():
    """ClientError with status 401 raises EmbedderAuthError."""
    from google.genai import errors as genai_errors

    exc = genai_errors.ClientError(401, {"error": {"message": "Unauthorized"}})

    client = MagicMock()
    client.aio.models.embed_content = AsyncMock(side_effect=exc)
    client.aio.live._api_client._http_client.aclose = AsyncMock()

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(EmbedderAuthError, match="authentication failed"):
        await embedder.embed("test")


@pytest.mark.asyncio
async def test_client_error_403_raises_auth_error():
    """ClientError with status 403 raises EmbedderAuthError."""
    from google.genai import errors as genai_errors

    exc = genai_errors.ClientError(403, {"error": {"message": "Forbidden"}})

    client = MagicMock()
    client.aio.models.embed_content = AsyncMock(side_effect=exc)
    client.aio.live._api_client._http_client.aclose = AsyncMock()

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(EmbedderAuthError, match="authentication failed"):
        await embedder.embed("test")


@pytest.mark.asyncio
async def test_client_error_429_raises_rate_limit_error():
    """ClientError with status 429 raises EmbedderRateLimitError."""
    from google.genai import errors as genai_errors

    exc = genai_errors.ClientError(429, {"error": {"message": "Rate limit exceeded"}})

    client = MagicMock()
    client.aio.models.embed_content = AsyncMock(side_effect=exc)
    client.aio.live._api_client._http_client.aclose = AsyncMock()

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(EmbedderRateLimitError, match="rate limit"):
        await embedder.embed("test")


@pytest.mark.asyncio
async def test_server_error_raises_retryable_provider_error():
    """ServerError raises retryable EmbedderProviderError."""
    from google.genai import errors as genai_errors

    client = MagicMock()
    client.aio.models.embed_content = AsyncMock(
        side_effect=genai_errors.ServerError(500, {"error": {"message": "Internal error"}})
    )
    client.aio.live._api_client._http_client.aclose = AsyncMock()

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(EmbedderProviderError) as exc_info:
        await embedder.embed("test")

    assert exc_info.value.retryable is True


@pytest.mark.asyncio
async def test_timeout_raises_timeout_error():
    """TimeoutError raises EmbedderTimeoutError."""
    client = MagicMock()
    client.aio.models.embed_content = AsyncMock(side_effect=TimeoutError("timed out"))
    client.aio.live._api_client._http_client.aclose = AsyncMock()

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(EmbedderTimeoutError, match="timed out"):
        await embedder.embed("test")


@pytest.mark.asyncio
async def test_connection_error_raises_connection_error():
    """ConnectionError raises EmbedderConnectionError."""
    client = MagicMock()
    client.aio.models.embed_content = AsyncMock(
        side_effect=ConnectionError("connection refused")
    )
    client.aio.live._api_client._http_client.aclose = AsyncMock()

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(EmbedderConnectionError, match="connection failed"):
        await embedder.embed("test")


@pytest.mark.asyncio
async def test_httpx_timeout_raises_timeout_error():
    """httpx.TimeoutException from SDK transport raises EmbedderTimeoutError."""
    import httpx

    client = MagicMock()
    client.aio.models.embed_content = AsyncMock(
        side_effect=httpx.ReadTimeout("read timed out")
    )
    client.aio.live._api_client._http_client.aclose = AsyncMock()

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(EmbedderTimeoutError, match="timed out"):
        await embedder.embed("test")


@pytest.mark.asyncio
async def test_httpx_connect_error_raises_connection_error():
    """httpx.ConnectError from SDK transport raises EmbedderConnectionError."""
    import httpx

    client = MagicMock()
    client.aio.models.embed_content = AsyncMock(
        side_effect=httpx.ConnectError("refused")
    )
    client.aio.live._api_client._http_client.aclose = AsyncMock()

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(EmbedderConnectionError, match="connection failed"):
        await embedder.embed("test")


@pytest.mark.asyncio
async def test_httpx_request_error_raises_connection_error():
    """httpx.RequestError from SDK transport raises EmbedderConnectionError."""
    import httpx

    client = MagicMock()
    client.aio.models.embed_content = AsyncMock(
        side_effect=httpx.RequestError("network error", request=MagicMock())
    )
    client.aio.live._api_client._http_client.aclose = AsyncMock()

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(EmbedderConnectionError, match="transport error"):
        await embedder.embed("test")


@pytest.mark.asyncio
async def test_error_chaining_preserves_original():
    """Translated errors chain the original exception via __cause__."""
    from google.genai import errors as genai_errors

    original = genai_errors.ServerError(500, {"error": {"message": "Internal error"}})

    client = MagicMock()
    client.aio.models.embed_content = AsyncMock(side_effect=original)
    client.aio.live._api_client._http_client.aclose = AsyncMock()

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(EmbedderProviderError) as exc_info:
        await embedder.embed("test")

    assert exc_info.value.__cause__ is original


# ===========================================================================
# close()
# ===========================================================================


@pytest.mark.asyncio
async def test_close_attempts_client_cleanup():
    """close() attempts to close the underlying HTTP client (best-effort)."""
    client = MagicMock()
    client.aio.models.embed_content = AsyncMock()
    aclose_mock = AsyncMock()
    client.aio.live._api_client._http_client.aclose = aclose_mock

    embedder = _build_embedder(client_mock=client)
    await embedder.close()

    aclose_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_swallows_errors():
    """close() swallows exceptions from the internal client."""
    client = MagicMock()
    client.aio.models.embed_content = AsyncMock()
    client.aio.live._api_client._http_client.aclose = AsyncMock(
        side_effect=AttributeError("SDK changed")
    )

    embedder = _build_embedder(client_mock=client)
    # Should not raise
    await embedder.close()
