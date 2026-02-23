"""Embedder protocol interfaces.

These are the contracts that all embedder implementations must satisfy.
Consumers depend on these protocols, never on concrete implementations.
"""

from typing import Protocol, runtime_checkable

from airweave.domains.embedders.schemas import DenseEmbedding, SparseEmbedding


@runtime_checkable
class DenseEmbedderProtocol(Protocol):
    """Dense embedding provider (OpenAI, Mistral, Local)."""

    @property
    def vector_size(self) -> int:
        """Return the output dimension of this embedder."""
        ...

    async def embed(self, text: str) -> DenseEmbedding:
        """Embed a single text."""
        ...

    async def embed_many(self, texts: list[str]) -> list[DenseEmbedding]:
        """Embed a batch of texts."""
        ...

    async def close(self) -> None:
        """Release resources."""
        ...


@runtime_checkable
class SparseEmbedderProtocol(Protocol):
    """Sparse embedding provider (FastEmbed BM25)."""

    async def embed(self, text: str) -> SparseEmbedding:
        """Embed a single text."""
        ...

    async def embed_many(self, texts: list[str]) -> list[SparseEmbedding]:
        """Embed a batch of texts."""
        ...

    async def close(self) -> None:
        """Release resources."""
        ...


@runtime_checkable
class EmbedderServiceProtocol(Protocol):
    """Factory that returns configured embedder instances."""

    @property
    def vector_size(self) -> int:
        """Return the embedding dimensions."""
        ...

    @property
    def model_name(self) -> str:
        """Return the embedding model name."""
        ...

    def get_dense_embedder(self) -> DenseEmbedderProtocol:
        """Return a dense embedder for the configured model."""
        ...

    def get_sparse_embedder(self) -> SparseEmbedderProtocol:
        """Return a sparse BM25 embedder."""
        ...
