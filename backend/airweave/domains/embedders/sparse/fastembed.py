"""FastEmbed sparse embedder satisfying SparseEmbedderProtocol.

Runs a local BM25 sparse embedding model via fastembed. The model is
synchronous, so all calls are dispatched to a thread pool. Callers pass
text, get SparseEmbedding back, handle errors themselves.
"""

import asyncio

from fastembed import SparseTextEmbedding

from airweave.domains.embedders.exceptions import (
    EmbedderConfigError,
    EmbedderInputError,
    EmbedderProviderError,
    EmbedderResponseError,
)
from airweave.domains.embedders.protocols import SparseEmbedderProtocol
from airweave.domains.embedders.types import SparseEmbedding

_PROVIDER = "fastembed"


class FastEmbedSparseEmbedder(SparseEmbedderProtocol):
    """FastEmbed sparse embedder satisfying SparseEmbedderProtocol.

    Runs a local BM25 sparse embedding model via fastembed. The model is
    synchronous, so all calls are dispatched to a thread pool. Callers pass
    text, get SparseEmbedding back, handle errors themselves.
    """

    _MAX_TEXTS_PER_SUB_BATCH: int = 200

    def __init__(self, *, model: str) -> None:
        """Initialize the FastEmbed sparse embedder.

        Args:
            model: Model name (e.g. "Qdrant/bm25").

        Raises:
            EmbedderConfigError: If the model cannot be loaded.
        """
        self._model_name = model
        try:
            self._model = SparseTextEmbedding(model)
        except Exception as e:
            raise EmbedderConfigError(
                f"Failed to load sparse embedding model '{model}': {e}"
            ) from e

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def model_name(self) -> str:
        """The model identifier (e.g. "Qdrant/bm25")."""
        return self._model_name

    async def embed(self, text: str) -> SparseEmbedding:
        """Embed a single text into a sparse vector."""
        results = await self.embed_many([text])
        return results[0]

    async def embed_many(self, texts: list[str]) -> list[SparseEmbedding]:
        """Embed a batch of texts into sparse vectors."""
        if not texts:
            return []

        self._validate_inputs(texts)

        # Process sub-batches sequentially — local CPU model, no
        # concurrency benefit, and keeps the event loop responsive.
        results: list[SparseEmbedding] = []
        for i in range(0, len(texts), self._MAX_TEXTS_PER_SUB_BATCH):
            sub_batch = texts[i : i + self._MAX_TEXTS_PER_SUB_BATCH]
            results.extend(await self._embed_batch(sub_batch))

        return results

    async def close(self) -> None:
        """No-op — fastembed holds no external resources."""

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_inputs(self, texts: list[str]) -> None:
        """Validate all input texts.

        Raises:
            EmbedderInputError: If any text is empty or blank.
        """
        for i, text in enumerate(texts):
            if not text or not text.strip():
                raise EmbedderInputError(f"Text at index {i} is empty or blank")

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------

    async def _embed_batch(self, batch: list[str]) -> list[SparseEmbedding]:
        """Embed a batch in a thread pool, then validate and convert."""
        try:
            raw_embeddings = await asyncio.to_thread(self._embed_sync, batch)
        except EmbedderResponseError:
            raise
        except Exception as e:
            raise EmbedderProviderError(
                f"FastEmbed sparse embedding failed: {e}",
                provider=_PROVIDER,
                retryable=False,
            ) from e

        return raw_embeddings

    def _embed_sync(self, texts: list[str]) -> list[SparseEmbedding]:
        """Run the synchronous fastembed model and convert results."""
        raw = list(self._model.embed(texts))

        if len(raw) != len(texts):
            raise EmbedderResponseError(f"Expected {len(texts)} embeddings, got {len(raw)}")

        return [
            SparseEmbedding(
                indices=emb.indices.tolist(),
                values=emb.values.tolist(),
            )
            for emb in raw
        ]
