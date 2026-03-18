"""Protocols for embedders and embedder registries."""

from enum import Enum
from typing import Protocol, runtime_checkable

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


@runtime_checkable
class MultimodalDenseEmbedderProtocol(DenseEmbedderProtocol, Protocol):
    """Protocol for dense embedders that support native file embedding.

    Extends DenseEmbedderProtocol with multimodal capabilities — embed files
    (PDFs, images, audio, video) directly via the provider API, bypassing
    text extraction. The pipeline detects this capability at runtime via
    isinstance() checks.
    """

    @property
    def supports_multimodal(self) -> bool:
        """Whether this embedder supports native file embedding."""
        ...

    @property
    def supported_mime_types(self) -> set[str]:
        """Set of MIME types this embedder can embed natively."""
        ...

    async def embed_file(
        self,
        file_path: str,
        mime_type: str,
        *,
        purpose: EmbeddingPurpose = EmbeddingPurpose.DOCUMENT,
    ) -> DenseEmbedding:
        """Embed a file natively via the provider API.

        Args:
            file_path: Path to the file on disk.
            mime_type: MIME type of the file.
            purpose: Whether this is a document or query embedding.

        Returns:
            A single DenseEmbedding for the file.

        Raises:
            EmbedderInputError: If the file is invalid (wrong MIME, too large, etc.).
        """
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
