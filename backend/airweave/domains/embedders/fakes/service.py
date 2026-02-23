"""Fake embedder implementations for tests.

All fakes produce deterministic output based on input text hashes,
making tests reproducible without any external API calls.
"""

import hashlib
import random

from airweave.domains.embedders.schemas import DenseEmbedding, SparseEmbedding


class FakeDenseEmbedder:
    """Deterministic dense embedder for tests."""

    def __init__(self, vector_size: int = 128) -> None:
        """Initialize with configurable vector size."""
        self._vector_size = vector_size

    @property
    def vector_size(self) -> int:
        """Return the output dimension."""
        return self._vector_size

    async def embed(self, text: str) -> DenseEmbedding:
        """Embed a single text deterministically."""
        return self._deterministic_embedding(text)

    async def embed_many(self, texts: list[str]) -> list[DenseEmbedding]:
        """Embed a batch of texts deterministically."""
        return [self._deterministic_embedding(text) for text in texts]

    async def close(self) -> None:
        """No-op."""

    def _deterministic_embedding(self, text: str) -> DenseEmbedding:
        """Generate a deterministic embedding from text hash."""
        seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
        rng = random.Random(seed)
        vector = [rng.uniform(-1.0, 1.0) for _ in range(self._vector_size)]
        return DenseEmbedding(vector=vector)


class FakeSparseEmbedder:
    """Deterministic sparse embedder for tests."""

    async def embed(self, text: str) -> SparseEmbedding:
        """Embed a single text deterministically."""
        return self._deterministic_embedding(text)

    async def embed_many(self, texts: list[str]) -> list[SparseEmbedding]:
        """Embed a batch of texts deterministically."""
        return [self._deterministic_embedding(text) for text in texts]

    async def close(self) -> None:
        """No-op."""

    def _deterministic_embedding(self, text: str) -> SparseEmbedding:
        """Generate a deterministic sparse embedding from text hash."""
        seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
        rng = random.Random(seed)
        n_tokens = rng.randint(3, 10)
        indices = sorted(rng.sample(range(30000), n_tokens))
        values = [rng.uniform(0.1, 2.0) for _ in range(n_tokens)]
        return SparseEmbedding(indices=indices, values=values)


class FakeEmbedderService:
    """Fake embedder service for tests."""

    def __init__(self, vector_size: int = 128, model_name: str = "fake-model") -> None:
        """Initialize with configurable vector size and model name."""
        self._vector_size = vector_size
        self._model_name = model_name
        self._dense_embedder: FakeDenseEmbedder | None = None
        self._sparse_embedder: FakeSparseEmbedder | None = None

    @property
    def vector_size(self) -> int:
        """Return the embedding dimensions."""
        return self._vector_size

    @property
    def model_name(self) -> str:
        """Return the embedding model name."""
        return self._model_name

    def get_dense_embedder(self) -> FakeDenseEmbedder:
        """Return a fake dense embedder (lazy-created, cached)."""
        if self._dense_embedder is None:
            self._dense_embedder = FakeDenseEmbedder(self._vector_size)
        return self._dense_embedder

    def get_sparse_embedder(self) -> FakeSparseEmbedder:
        """Return a fake sparse embedder (lazy-created, cached)."""
        if self._sparse_embedder is None:
            self._sparse_embedder = FakeSparseEmbedder()
        return self._sparse_embedder
