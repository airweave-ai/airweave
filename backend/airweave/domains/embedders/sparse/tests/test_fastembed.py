"""Unit tests for FastEmbedSparseEmbedder.

All fastembed model interactions are mocked — no model loading or inference.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from airweave.domains.embedders.exceptions import (
    EmbedderConfigError,
    EmbedderInputError,
    EmbedderProviderError,
    EmbedderResponseError,
)
from airweave.domains.embedders.sparse.fastembed import FastEmbedSparseEmbedder
from airweave.domains.embedders.types import SparseEmbedding

_MODEL = "Qdrant/bm25"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_raw_embedding(
    indices: list[int] | None = None,
    values: list[float] | None = None,
) -> SimpleNamespace:
    """Create a fake fastembed SparseEmbedding with numpy arrays."""
    return SimpleNamespace(
        indices=np.array(indices or [1, 2, 3], dtype=np.int64),
        values=np.array(values or [0.5, 0.3, 0.2], dtype=np.float64),
    )


def _build_embedder(model_mock: MagicMock | None = None) -> FastEmbedSparseEmbedder:
    """Build a FastEmbedSparseEmbedder with a mocked model."""
    with patch(
        "airweave.domains.embedders.sparse.fastembed.SparseTextEmbedding"
    ) as mock_cls:
        if model_mock is None:
            model_mock = MagicMock()
        mock_cls.return_value = model_mock

        embedder = FastEmbedSparseEmbedder(model=_MODEL)
    return embedder


# ===========================================================================
# Construction
# ===========================================================================


def test_model_load_failure_raises_config_error():
    """Failed model load raises EmbedderConfigError."""
    with patch(
        "airweave.domains.embedders.sparse.fastembed.SparseTextEmbedding"
    ) as mock_cls:
        mock_cls.side_effect = RuntimeError("model not found")

        with pytest.raises(EmbedderConfigError, match="Failed to load"):
            FastEmbedSparseEmbedder(model=_MODEL)


# ===========================================================================
# embed() — single text
# ===========================================================================


@pytest.mark.asyncio
async def test_embed_returns_single_sparse_embedding():
    """embed() delegates to embed_many and returns the first result."""
    model = MagicMock()
    model.embed.return_value = iter([_make_raw_embedding()])

    embedder = _build_embedder(model_mock=model)
    result = await embedder.embed("hello world")

    assert isinstance(result, SparseEmbedding)
    assert result.indices == [1, 2, 3]
    assert result.values == [0.5, 0.3, 0.2]


# ===========================================================================
# embed_many() — basic batching
# ===========================================================================


@pytest.mark.asyncio
async def test_embed_many_empty_returns_empty():
    """Empty input returns empty list without calling the model."""
    model = MagicMock()
    embedder = _build_embedder(model_mock=model)

    result = await embedder.embed_many([])

    assert result == []
    model.embed.assert_not_called()


@pytest.mark.asyncio
async def test_embed_many_small_batch():
    """Small batch returns correct number of SparseEmbedding objects."""
    texts = ["text a", "text b", "text c"]
    raw = [_make_raw_embedding() for _ in texts]
    model = MagicMock()
    model.embed.return_value = iter(raw)

    embedder = _build_embedder(model_mock=model)
    result = await embedder.embed_many(texts)

    assert len(result) == 3
    assert all(isinstance(r, SparseEmbedding) for r in result)
    model.embed.assert_called_once()


@pytest.mark.asyncio
async def test_embed_many_sub_batching():
    """More than 200 texts are split into sequential sub-batches."""
    texts = [f"text {i}" for i in range(350)]

    call_count = 0

    def fake_embed(batch):
        nonlocal call_count
        call_count += 1
        return iter([_make_raw_embedding() for _ in batch])

    model = MagicMock()
    model.embed.side_effect = fake_embed

    embedder = _build_embedder(model_mock=model)
    result = await embedder.embed_many(texts)

    assert len(result) == 350
    assert call_count == 2  # 200 + 150


# ===========================================================================
# Numpy → Python list conversion
# ===========================================================================


@pytest.mark.asyncio
async def test_numpy_arrays_converted_to_lists():
    """Numpy arrays from fastembed are converted to plain Python lists."""
    raw = _make_raw_embedding(indices=[10, 20], values=[0.9, 0.1])
    model = MagicMock()
    model.embed.return_value = iter([raw])

    embedder = _build_embedder(model_mock=model)
    result = await embedder.embed("test")

    assert isinstance(result.indices, list)
    assert isinstance(result.values, list)
    assert result.indices == [10, 20]
    assert result.values == [0.9, 0.1]


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
# Response validation
# ===========================================================================


@pytest.mark.asyncio
async def test_count_mismatch_raises_response_error():
    """Mismatched embedding count raises EmbedderResponseError."""
    model = MagicMock()
    # Return 2 embeddings for 3 texts
    model.embed.return_value = iter([_make_raw_embedding(), _make_raw_embedding()])

    embedder = _build_embedder(model_mock=model)

    with pytest.raises(EmbedderResponseError, match="Expected 3.*got 2"):
        await embedder.embed_many(["a", "b", "c"])


# ===========================================================================
# Error translation
# ===========================================================================


@pytest.mark.asyncio
async def test_model_exception_raises_provider_error():
    """Runtime exception during embedding raises EmbedderProviderError."""
    model = MagicMock()
    model.embed.side_effect = RuntimeError("inference failed")

    embedder = _build_embedder(model_mock=model)

    with pytest.raises(EmbedderProviderError, match="embedding failed"):
        await embedder.embed("test")


@pytest.mark.asyncio
async def test_error_chaining_preserves_original():
    """Translated errors chain the original exception via __cause__."""
    model = MagicMock()
    original = RuntimeError("boom")
    model.embed.side_effect = original

    embedder = _build_embedder(model_mock=model)

    with pytest.raises(EmbedderProviderError) as exc_info:
        await embedder.embed("test")

    assert exc_info.value.__cause__ is original


@pytest.mark.asyncio
async def test_count_mismatch_not_wrapped_as_provider_error():
    """EmbedderResponseError from count mismatch is not re-wrapped."""
    model = MagicMock()
    model.embed.return_value = iter([])  # 0 embeddings for 1 text

    embedder = _build_embedder(model_mock=model)

    with pytest.raises(EmbedderResponseError):
        await embedder.embed("test")


# ===========================================================================
# close()
# ===========================================================================


@pytest.mark.asyncio
async def test_close_is_noop():
    """close() completes without error."""
    embedder = _build_embedder()
    await embedder.close()  # should not raise
