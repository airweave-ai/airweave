"""Protocols for embedders and embedder registries."""

from enum import Enum
from typing import Protocol

from airweave.core.protocols.registry import RegistryProtocol
from airweave.domains.embedders.types import (
    DenseEmbedderEntry,
    DenseEmbedding,
    SparseEmbedderEntry,
    SparseEmbedding,
)

# ---------------------------------------------------------------------------
# Embedding purpose enum
# ---------------------------------------------------------------------------


class EmbeddingPurpose(str, Enum):
    """Whether the text being embedded is a document or a query.

    Gemini Embedding 2 uses this to select the appropriate task type
    (RETRIEVAL_DOCUMENT vs RETRIEVAL_QUERY). Other providers accept
    the parameter but ignore it.
    """

    DOCUMENT = "document"
    QUERY = "query"


# ---------------------------------------------------------------------------
# Embedder protocols
# ---------------------------------------------------------------------------


class DenseEmbedderProtocol(Protocol):
    """Protocol for dense embedding models."""

    @property
    def model_name(self) -> str:
        """The model identifier (e.g. "text-embedding-3-large")."""
        ...

    @property
    def dimensions(self) -> int:
        """The output vector dimensionality."""
        ...

    async def embed(
        self, text: str, *, purpose: EmbeddingPurpose = EmbeddingPurpose.DOCUMENT
    ) -> DenseEmbedding:
        """Embed a single text into a dense vector."""
        ...

    async def embed_many(
        self, texts: list[str], *, purpose: EmbeddingPurpose = EmbeddingPurpose.DOCUMENT
    ) -> list[DenseEmbedding]:
        """Embed a batch of texts into dense vectors."""
        ...

    async def close(self) -> None:
        """Release any held resources (HTTP clients, etc.)."""
        ...


class SparseEmbedderProtocol(Protocol):
    """Protocol for sparse embedding models."""

    @property
    def model_name(self) -> str:
        """The model identifier (e.g. "Qdrant/bm25")."""
        ...

    async def embed(self, text: str) -> SparseEmbedding:
        """Embed a single text into a sparse vector."""
        ...

    async def embed_many(self, texts: list[str]) -> list[SparseEmbedding]:
        """Embed a batch of texts into sparse vectors."""
        ...

    async def close(self) -> None:
        """Release any held resources (HTTP clients, etc.)."""
        ...


# ---------------------------------------------------------------------------
# Registry protocols
# ---------------------------------------------------------------------------


class DenseEmbedderRegistryProtocol(RegistryProtocol[DenseEmbedderEntry], Protocol):
    """Dense embedder registry protocol."""

    def list_for_provider(self, provider: str) -> list[DenseEmbedderEntry]:
        """List all dense embedder entries for a provider."""
        ...


class SparseEmbedderRegistryProtocol(RegistryProtocol[SparseEmbedderEntry], Protocol):
    """Sparse embedder registry protocol."""

    def list_for_provider(self, provider: str) -> list[SparseEmbedderEntry]:
        """List all sparse embedder entries for a provider."""
        ...
