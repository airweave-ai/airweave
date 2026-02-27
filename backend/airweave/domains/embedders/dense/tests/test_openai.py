"""Unit tests for OpenAIDenseEmbedder.

All OpenAI SDK and tiktoken interactions are mocked — no network calls.
"""

from dataclasses import dataclass, field
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
from airweave.domains.embedders.dense.openai import OpenAIDenseEmbedder
from airweave.domains.embedders.types import DenseEmbedding

_DIMS = 256
_MODEL = "text-embedding-3-large"
_API_KEY = "sk-test-key"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_embedding_object(vector: list[float], index: int = 0) -> SimpleNamespace:
    """Create a fake OpenAI embedding response object."""
    return SimpleNamespace(embedding=vector, index=index)


def _make_response(vectors: list[list[float]]) -> SimpleNamespace:
    """Create a fake OpenAI embeddings response."""
    data = [_make_embedding_object(v, i) for i, v in enumerate(vectors)]
    return SimpleNamespace(data=data, model=_MODEL, usage=SimpleNamespace(total_tokens=100))


def _vector(dims: int = _DIMS, val: float = 0.1) -> list[float]:
    """Create a dummy vector of the given dimensions."""
    return [val] * dims


def _fake_encode(text: str, **kwargs: object) -> list[int]:
    """Fake tiktoken encode: 1 token per word. Accepts allowed_special etc."""
    return list(range(len(text.split())))


def _build_embedder(
    client_mock: AsyncMock | None = None,
    encoder_mock: MagicMock | None = None,
) -> OpenAIDenseEmbedder:
    """Build an OpenAIDenseEmbedder with mocked dependencies."""
    with (
        patch("airweave.domains.embedders.dense.openai.AsyncOpenAI") as mock_openai,
        patch("airweave.domains.embedders.dense.openai.tiktoken") as mock_tiktoken,
    ):
        if client_mock is None:
            client_mock = AsyncMock()
        mock_openai.return_value = client_mock

        if encoder_mock is None:
            encoder_mock = MagicMock()
            encoder_mock.encode.side_effect = _fake_encode
        mock_tiktoken.get_encoding.return_value = encoder_mock

        embedder = OpenAIDenseEmbedder(
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
    client = AsyncMock()
    client.embeddings.create.return_value = _make_response([_vector()])

    embedder = _build_embedder(client_mock=client)
    result = await embedder.embed("hello world")

    assert isinstance(result, DenseEmbedding)
    assert len(result.vector) == _DIMS
    client.embeddings.create.assert_awaited_once()


# ===========================================================================
# embed_many() — basic batching
# ===========================================================================


@pytest.mark.asyncio
async def test_embed_many_empty_returns_empty():
    """Empty input returns empty list without API call."""
    client = AsyncMock()
    embedder = _build_embedder(client_mock=client)

    result = await embedder.embed_many([])

    assert result == []
    client.embeddings.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_embed_many_single_batch():
    """Fewer than 100 texts → single API call."""
    texts = [f"text {i}" for i in range(5)]
    vectors = [_vector() for _ in texts]
    client = AsyncMock()
    client.embeddings.create.return_value = _make_response(vectors)

    embedder = _build_embedder(client_mock=client)
    result = await embedder.embed_many(texts)

    assert len(result) == 5
    assert all(isinstance(r, DenseEmbedding) for r in result)
    client.embeddings.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_embed_many_sub_batching():
    """More than 100 texts → split into multiple sub-batches."""
    texts = [f"text {i}" for i in range(150)]

    call_count = 0

    async def fake_create(**kwargs):
        nonlocal call_count
        call_count += 1
        n = len(kwargs["input"])
        return _make_response([_vector() for _ in range(n)])

    client = AsyncMock()
    client.embeddings.create.side_effect = fake_create

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
async def test_text_exceeding_token_limit_raises_input_error():
    """Text exceeding 8192 tokens raises EmbedderInputError."""
    encoder_mock = MagicMock()
    # Return 9000 tokens for any text
    encoder_mock.encode.return_value = list(range(9000))

    embedder = _build_embedder(encoder_mock=encoder_mock)

    with pytest.raises(EmbedderInputError, match="9000 tokens.*exceeding the limit"):
        await embedder.embed("some long text")


# ===========================================================================
# Token-based batch splitting
# ===========================================================================


@pytest.mark.asyncio
async def test_token_based_batch_splitting():
    """Sub-batch exceeding 300K tokens splits recursively."""
    # 10 texts, each ~50K tokens → 500K total → must split
    encoder_mock = MagicMock()
    encoder_mock.encode.side_effect = lambda text, **kwargs: list(range(50_000))

    call_count = 0

    async def fake_create(**kwargs):
        nonlocal call_count
        call_count += 1
        n = len(kwargs["input"])
        return _make_response([_vector() for _ in range(n)])

    client = AsyncMock()
    client.embeddings.create.side_effect = fake_create

    embedder = _build_embedder(client_mock=client, encoder_mock=encoder_mock)
    # Override the per-text token limit so our 50K texts pass validation
    embedder._MAX_TOKENS_PER_TEXT = 100_000

    texts = [f"text {i}" for i in range(10)]
    result = await embedder.embed_many(texts)

    assert len(result) == 10
    # Should have split: 10 → 5+5, each 250K < 300K → 2 calls
    assert call_count == 2


# ===========================================================================
# Response validation
# ===========================================================================


@pytest.mark.asyncio
async def test_count_mismatch_raises_response_error():
    """Mismatched embedding count raises EmbedderResponseError."""
    client = AsyncMock()
    # Send 3 texts but get 2 embeddings back
    client.embeddings.create.return_value = _make_response([_vector(), _vector()])

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(EmbedderResponseError, match="Expected 3.*got 2"):
        await embedder.embed_many(["a", "b", "c"])


@pytest.mark.asyncio
async def test_dimension_mismatch_raises_dimension_error():
    """Wrong vector dimensions raises EmbedderDimensionError."""
    wrong_dims = _DIMS + 10
    client = AsyncMock()
    client.embeddings.create.return_value = _make_response([[0.1] * wrong_dims])

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
    """Test case for OpenAI error → EmbedderError translation."""

    desc: str
    openai_exc_factory: object  # callable that returns the exception
    expected_type: type
    match: str = ""


def _make_auth_error():
    import openai

    return openai.AuthenticationError(
        message="Invalid API key",
        response=MagicMock(status_code=401, headers={}),
        body=None,
    )


def _make_rate_limit_error():
    import openai

    response = MagicMock(status_code=429, headers={"retry-after": "2.5"})
    return openai.RateLimitError(
        message="Rate limit exceeded",
        response=response,
        body=None,
    )


def _make_timeout_error():
    import openai

    return openai.APITimeoutError(request=MagicMock())


def _make_connection_error():
    import openai

    return openai.APIConnectionError(request=MagicMock())


def _make_status_error_500():
    import openai

    return openai.APIStatusError(
        message="Internal server error",
        response=MagicMock(status_code=500, headers={}),
        body=None,
    )


ERROR_CASES = [
    ErrorTranslationCase(
        desc="AuthenticationError → EmbedderAuthError",
        openai_exc_factory=_make_auth_error,
        expected_type=EmbedderAuthError,
        match="authentication failed",
    ),
    ErrorTranslationCase(
        desc="RateLimitError → EmbedderRateLimitError",
        openai_exc_factory=_make_rate_limit_error,
        expected_type=EmbedderRateLimitError,
        match="rate limit",
    ),
    ErrorTranslationCase(
        desc="APITimeoutError → EmbedderTimeoutError",
        openai_exc_factory=_make_timeout_error,
        expected_type=EmbedderTimeoutError,
        match="timed out",
    ),
    ErrorTranslationCase(
        desc="APIConnectionError → EmbedderConnectionError",
        openai_exc_factory=_make_connection_error,
        expected_type=EmbedderConnectionError,
        match="connection failed",
    ),
    ErrorTranslationCase(
        desc="APIStatusError 500 → EmbedderProviderError",
        openai_exc_factory=_make_status_error_500,
        expected_type=EmbedderProviderError,
        match="status 500",
    ),
]


@pytest.mark.parametrize("case", ERROR_CASES, ids=lambda c: c.desc)
@pytest.mark.asyncio
async def test_error_translation(case: ErrorTranslationCase):
    """OpenAI SDK exceptions are translated to the EmbedderError hierarchy."""
    client = AsyncMock()
    client.embeddings.create.side_effect = case.openai_exc_factory()

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(case.expected_type, match=case.match):
        await embedder.embed("test")


@pytest.mark.asyncio
async def test_rate_limit_error_captures_retry_after():
    """RateLimitError extracts retry-after from response headers."""
    client = AsyncMock()
    client.embeddings.create.side_effect = _make_rate_limit_error()

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(EmbedderRateLimitError) as exc_info:
        await embedder.embed("test")

    assert exc_info.value.retry_after == 2.5


@pytest.mark.asyncio
async def test_status_error_500_is_retryable():
    """APIStatusError with status >= 500 is marked retryable."""
    client = AsyncMock()
    client.embeddings.create.side_effect = _make_status_error_500()

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(EmbedderProviderError) as exc_info:
        await embedder.embed("test")

    assert exc_info.value.retryable is True


@pytest.mark.asyncio
async def test_error_chaining_preserves_original():
    """Translated errors chain the original exception via __cause__."""
    client = AsyncMock()
    original = _make_auth_error()
    client.embeddings.create.side_effect = original

    embedder = _build_embedder(client_mock=client)

    with pytest.raises(EmbedderAuthError) as exc_info:
        await embedder.embed("test")

    assert exc_info.value.__cause__ is original


# ===========================================================================
# close()
# ===========================================================================


@pytest.mark.asyncio
async def test_close_calls_client_close():
    """close() delegates to the underlying AsyncOpenAI client."""
    client = AsyncMock()
    embedder = _build_embedder(client_mock=client)

    await embedder.close()

    client.close.assert_awaited_once()
