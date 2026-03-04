"""Fake embedder implementations for testing."""

from airweave.domains.embedders.types import DenseEmbedding, SparseEmbedding


class FakeDenseEmbedder:
    """Test implementation of DenseEmbedderProtocol.

    Returns zero-vectors of a fixed dimension.

    Usage:
        fake = FakeDenseEmbedder(dimensions=3072)
        result = await fake.embed("hello")
        assert len(result.vector) == 3072
    """

    def __init__(self, dimensions: int = 3072) -> None:
        """Initialize with a fixed dimension size."""
        self._dimensions = dimensions

    @property
    def model_name(self) -> str:
        """The model identifier."""
        return "fake-dense"

    @property
    def dimensions(self) -> int:
        """The output vector dimensionality."""
        return self._dimensions

    async def embed(self, text: str) -> DenseEmbedding:
        """Return a zero-vector of the configured dimensions."""
        return DenseEmbedding(vector=[0.0] * self._dimensions)

    async def embed_many(self, texts: list[str]) -> list[DenseEmbedding]:
        """Return zero-vectors for each text."""
        return [DenseEmbedding(vector=[0.0] * self._dimensions) for _ in texts]

    async def close(self) -> None:
        """No-op."""


class FakeSparseEmbedder:
    """Test implementation of SparseEmbedderProtocol.

    Returns empty sparse vectors.

    Usage:
        fake = FakeSparseEmbedder()
        result = await fake.embed("hello")
        assert result.indices == []
    """

    @property
    def model_name(self) -> str:
        """The model identifier."""
        return "fake-sparse"

    async def embed(self, text: str) -> SparseEmbedding:
        """Return an empty sparse embedding."""
        return SparseEmbedding(indices=[], values=[])

    async def embed_many(self, texts: list[str]) -> list[SparseEmbedding]:
        """Return empty sparse embeddings for each text."""
        return [SparseEmbedding(indices=[], values=[]) for _ in texts]

    async def close(self) -> None:
        """No-op."""
