"""Unit tests for MistralDenseEmbedder.

All Mistral SDK and tokenizer interactions are mocked — no network calls.
"""

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
from airweave.domains.embedders.dense.mistral import MistralDenseEmbedder
from airweave.domains.embedders.types import DenseEmbedding

_DIMS = 1024
_MODEL = "mistral-embed"
_API_KEY = "test-mistral-key"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_embedding_object(vector: list[float], index: int = 0) -> SimpleNamespace:
    """Create a fake Mistral embedding response object."""
    return SimpleNamespace(embedding=vector, index=index)


def _make_response(vectors: list[list[float]]) -> SimpleNamespace:
    """Create a fake Mistral embeddings response."""
    data = [_make_embedding_object(v, i) for i, v in enumerate(vectors)]
    return SimpleNamespace(data=data, model=_MODEL)


def _vector(dims: int = _DIMS, val: float = 0.1) -> list[float]:
    """Create a dummy vector of the given dimensions."""
    return [val] * dims


def _fake_count_tokens(text: str) -> int:
    """Fake token counter: 1 token per word."""
    return len(text.split())


def _build_embedder(
    client_mock: MagicMock | None = None,
    tokenizer_mock: MagicMock | None = None,
) -> MistralDenseEmbedder:
    """Build a MistralDenseEmbedder with mocked dependencies."""
    with (
        patch("airweave.domains.embedders.dense.mistral.Mistral") as mock_mistral_cls,
        patch(
            "airweave.domains.embedders.dense.mistral.get_tokenizer"
        ) as mock_get_tokenizer,
    ):
        if client_mock is None:
            client_mock = MagicMock()
            client_mock.embeddings.create_async = AsyncMock()
            client_mock.close_async = AsyncMock()
        mock_mistral_cls.return_value = client_mock

        if tokenizer_mock is None:
            tokenizer_mock = MagicMock()
            tokenizer_mock.count_tokens.side_effect = _fake_count_tokens
        mock_get_tokenizer.return_value = tokenizer_mock

        embedder = MistralDenseEmbedder(
            api_key=_API_KEY,
            model=_MODEL,
            dimensions=_DIMS,
        )
    return embedder


# ===========================================================================
# embed() — single text
# ===========================================================================


@pytest.mark.asyncio
async def test_embed_returns_single_dense_embedding():
    """embed() delegates to embed_many and returns the first result."""
    client = MagicMock()
    client.embeddings.create_async = AsyncMock(return_value=_make_response([_vector()]))
    client.close_async = AsyncMock()

    embedder = _build_embedder(client_mock=client)
    result = await embedder.embed("hello world")

    assert isinstance(result, DenseEmbedding)
    assert len(result.vector) == _DIMS
    client.embeddings.create_async.assert_awaited_once()


# ===========================================================================
# embed_many() — basic batching
# ===========================================================================


@pytest.mark.asyncio
async def test_embed_many_empty_returns_empty():
    """Empty input returns empty list without API call."""
    client = MagicMock()
    client.embeddings.create_async = AsyncMock()
    client.close_async = AsyncMock()
    embedder = _build_embedder(client_mock=client)

    result = await embedder.embed_many([])

    assert result == []
    client.embeddings.create_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_embed_many_single_batch():
    """Fewer than 128 texts -> single API call."""
    texts = [f"text {i}" for i in range(5)]
    vectors = [_vector() for _ in texts]
    client = MagicMock()
    client.embeddings.create_async = AsyncMock(return_value=_make_response(vectors))
    client.close_async = AsyncMock()

    embedder = _build_embedder(client_mock=client)
    result = await embedder.embed_many(texts)

    assert len(result) == 5
    assert all(isinstance(r, DenseEmbedding) for r in result)
    client.embeddings.create_async.assert_awaited_once()


@pytest.mark.asyncio
async def test_embed_many_sub_batching():
    """More than 128 texts -> split into multiple sub-batches."""
    texts = [f"text {i}" for i in range(200)]

    call_count = 0

    async def fake_create(**kwargs):
        nonlocal call_count
        call_count += 1
        n = len(kwargs.get("inputs", kwargs.get("input", [])))
        return _make_response([_vector() for _ in range(n)])

    client = MagicMock()
    client.embeddings.create_async = AsyncMock(side_effect=fake_create)
    client.close_async = AsyncMock()

    embedder = _build_embedder(client_mock=client)
    result = await embedder.embed_many(texts)

    assert len(result) == 200
    assert call_count == 2  # 128 + 72


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
async def test_text_exceeding_token_limit_raises_input_error():
    """Text exceeding 8000 tokens raises EmbedderInputError."""
    tokenizer_mock = MagicMock()
    tokenizer_mock.count_tokens.return_value = 9000

    embedder = _build_embedder(tokenizer_mock=tokenizer_mock)

    with pytest.raises(EmbedderInputError, match="9000 tokens.*exceeding the limit"):
        await embedder.embed("some long text")


# ===========================================================================
# Token-based batch splitting
# ===========================================================================


@pytest.mark.asyncio
async def test_token_based_batch_splitting():
    """Sub-batch exceeding 8K tokens splits recursively."""
    tokenizer_mock = MagicMock()
    tokenizer_mock.count_tokens.return_value = 5000

    call_count = 0

    async def fake_create(**kwargs):
        nonlocal call_count
        call_count += 1
        n = len(kwargs.get("inputs", kwargs.get("input", [])))
        return _make_response([_vector() for _ in range(n)])

    client = MagicMock()
    client.embeddings.create_async = AsyncMock(side_effect=fake_create)
    client.close_async = AsyncMock()

    embedder = _build_embedder(client_mock=client, tokenizer_mock=tokenizer_mock)

    texts = [f"text {i}" for i in range(10)]
    result = await embedder.embed_many(texts)

    assert len(result) == 10
    # 10 texts * 5000 tokens = 50K > 8K, splits recursively down
    assert call_count > 1


# ===========================================================================
# Response validation
# ===========================================================================


@pytest.mark.asyncio
async def test_count_mismatch_raises_response_error():
    """Mismatched embedding count raises EmbedderResponseError."""
    client = MagicMock()
    client.embeddings.create_async = AsyncMock(
        return_value=_make_response([_vector(), _vector()])
    )
    client.close_async = AsyncMock()

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(EmbedderResponseError, match="Expected 3.*got 2"):
        await embedder.embed_many(["a", "b", "c"])


@pytest.mark.asyncio
async def test_dimension_mismatch_raises_dimension_error():
    """Wrong vector dimensions raises EmbedderDimensionError."""
    wrong_dims = _DIMS + 10
    client = MagicMock()
    client.embeddings.create_async = AsyncMock(
        return_value=_make_response([[0.1] * wrong_dims])
    )
    client.close_async = AsyncMock()

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(EmbedderDimensionError) as exc_info:
        await embedder.embed("hello")

    assert exc_info.value.expected == _DIMS
    assert exc_info.value.actual == wrong_dims


# ===========================================================================
# Error translation
# ===========================================================================


@dataclass
class ErrorTranslationCase:
    """Test case for Mistral error -> EmbedderError translation."""

    desc: str
    exc_factory: object  # callable that returns the exception
    expected_type: type
    match: str = ""


def _make_sdk_error(status_code: int, message: str = "error"):
    import httpx
    from mistralai.models import SDKError

    raw_response = httpx.Response(
        status_code, request=httpx.Request("POST", "http://test")
    )
    return SDKError(message=message, raw_response=raw_response)


def _make_httpx_timeout():
    import httpx

    return httpx.ReadTimeout("timed out")


def _make_httpx_connect_error():
    import httpx

    return httpx.ConnectError("connection refused")


ERROR_CASES = [
    ErrorTranslationCase(
        desc="SDKError 401 -> EmbedderAuthError",
        exc_factory=lambda: _make_sdk_error(401),
        expected_type=EmbedderAuthError,
        match="authentication failed",
    ),
    ErrorTranslationCase(
        desc="SDKError 429 -> EmbedderRateLimitError",
        exc_factory=lambda: _make_sdk_error(429),
        expected_type=EmbedderRateLimitError,
        match="rate limit",
    ),
    ErrorTranslationCase(
        desc="SDKError 500 -> EmbedderProviderError (retryable)",
        exc_factory=lambda: _make_sdk_error(500),
        expected_type=EmbedderProviderError,
        match="status 500",
    ),
    ErrorTranslationCase(
        desc="SDKError other -> EmbedderProviderError (not retryable)",
        exc_factory=lambda: _make_sdk_error(400),
        expected_type=EmbedderProviderError,
        match="Mistral API error",
    ),
    ErrorTranslationCase(
        desc="httpx.TimeoutException -> EmbedderTimeoutError",
        exc_factory=_make_httpx_timeout,
        expected_type=EmbedderTimeoutError,
        match="timed out",
    ),
    ErrorTranslationCase(
        desc="httpx.ConnectError -> EmbedderConnectionError",
        exc_factory=_make_httpx_connect_error,
        expected_type=EmbedderConnectionError,
        match="connection failed",
    ),
]


@pytest.mark.parametrize("case", ERROR_CASES, ids=lambda c: c.desc)
@pytest.mark.asyncio
async def test_error_translation(case: ErrorTranslationCase):
    """Mistral SDK exceptions are translated to the EmbedderError hierarchy."""
    client = MagicMock()
    client.embeddings.create_async = AsyncMock(side_effect=case.exc_factory())
    client.close_async = AsyncMock()

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(case.expected_type, match=case.match):
        await embedder.embed("test")


@pytest.mark.asyncio
async def test_sdk_error_500_is_retryable():
    """SDKError with status >= 500 is marked retryable."""
    client = MagicMock()
    client.embeddings.create_async = AsyncMock(
        side_effect=_make_sdk_error(500)
    )
    client.close_async = AsyncMock()

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(EmbedderProviderError) as exc_info:
        await embedder.embed("test")

    assert exc_info.value.retryable is True


@pytest.mark.asyncio
async def test_sdk_error_400_is_not_retryable():
    """SDKError with status < 500 (non-auth, non-rate-limit) is not retryable."""
    client = MagicMock()
    client.embeddings.create_async = AsyncMock(
        side_effect=_make_sdk_error(400)
    )
    client.close_async = AsyncMock()

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(EmbedderProviderError) as exc_info:
        await embedder.embed("test")

    assert exc_info.value.retryable is False


@pytest.mark.asyncio
async def test_error_chaining_preserves_original():
    """Translated errors chain the original exception via __cause__."""
    client = MagicMock()
    original = _make_sdk_error(401)
    client.embeddings.create_async = AsyncMock(side_effect=original)
    client.close_async = AsyncMock()

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(EmbedderAuthError) as exc_info:
        await embedder.embed("test")

    assert exc_info.value.__cause__ is original


# ===========================================================================
# inputs vs input fallback
# ===========================================================================


@pytest.mark.asyncio
async def test_inputs_fallback_to_input():
    """When create_async rejects 'inputs', falls back to 'input'."""
    client = MagicMock()
    client.close_async = AsyncMock()

    call_kwargs: list[dict] = []

    async def fake_create(**kwargs):
        if "inputs" in kwargs:
            raise TypeError("unexpected keyword argument 'inputs'")
        call_kwargs.append(kwargs)
        n = len(kwargs["input"])
        return _make_response([_vector() for _ in range(n)])

    client.embeddings.create_async = AsyncMock(side_effect=fake_create)

    embedder = _build_embedder(client_mock=client)
    result = await embedder.embed("hello")

    assert len(result.vector) == _DIMS
    assert call_kwargs[0]["input"] == ["hello"]


# ===========================================================================
# close()
# ===========================================================================


@pytest.mark.asyncio
async def test_close_calls_client_close():
    """close() delegates to the underlying Mistral client."""
    client = MagicMock()
    client.embeddings.create_async = AsyncMock()
    client.close_async = AsyncMock()
    embedder = _build_embedder(client_mock=client)

    await embedder.close()

    client.close_async.assert_awaited_once()
