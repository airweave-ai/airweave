"""Mistral dense embedder for client-side embeddings."""

import asyncio
from typing import List

try:
    from mistralai import Mistral
except ImportError:
    Mistral = None  # type: ignore[assignment]

from airweave.domains.embedders.dense.registry import DenseModelSpec
from airweave.domains.embedders.exceptions import EmbedderProviderError
from airweave.domains.embedders.schemas import DenseEmbedding
from airweave.platform.rate_limiters.mistral import MistralRateLimiter
from airweave.platform.sync.async_helpers import run_in_thread_pool


class MistralDenseEmbedder:
    """Mistral dense embedder with fixed-dimension models."""

    MAX_BATCH_SIZE = 128
    MAX_CONCURRENT_REQUESTS = 5
    MAX_TOKENS_PER_REQUEST = 8000

    def __init__(
        self,
        model_spec: DenseModelSpec,
        target_dimensions: int,
        api_key: str | None = None,
    ) -> None:
        """Initialize Mistral embedder.

        Args:
            model_spec: Model specification from registry.
            target_dimensions: Output vector dimensions.
            api_key: Mistral API key.  Falls back to settings if not provided.
        """
        if api_key is None:
            from airweave.core.config import settings

            api_key = settings.MISTRAL_API_KEY

        if not api_key:
            raise EmbedderProviderError("MISTRAL_API_KEY required for Mistral embeddings")
        if Mistral is None:
            raise EmbedderProviderError("mistralai package required but not installed")

        self._model_spec = model_spec
        self._target_dimensions = target_dimensions
        self._client = Mistral(api_key=api_key)
        self._rate_limiter = MistralRateLimiter()

    @property
    def vector_size(self) -> int:
        """Return the output dimension of this embedder."""
        return self._target_dimensions

    async def embed(self, text: str) -> DenseEmbedding:
        """Embed a single text."""
        results = await self.embed_many([text])
        return results[0]

    async def embed_many(self, texts: list[str]) -> list[DenseEmbedding]:
        """Embed batch of texts using Mistral embeddings."""
        if not texts:
            return []

        for i, text in enumerate(texts):
            if not text or not text.strip():
                raise EmbedderProviderError(
                    f"Empty text at index {i}. Textual representation must be set before embedding."
                )

        # Mistral has fixed 1024 dimensions
        MISTRAL_FIXED_DIMENSIONS = 1024
        if self._target_dimensions != MISTRAL_FIXED_DIMENSIONS:
            raise EmbedderProviderError(
                f"Mistral embeddings are fixed at {MISTRAL_FIXED_DIMENSIONS} dimensions. "
                f"Requested {self._target_dimensions}. Use OpenAI for custom dimensions."
            )

        return await self._embed_batches(texts)

    async def _embed_batches(self, texts: list[str]) -> list[DenseEmbedding]:
        """Embed texts in parallel batches."""
        batches = [
            texts[i : i + self.MAX_BATCH_SIZE] for i in range(0, len(texts), self.MAX_BATCH_SIZE)
        ]
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)

        async def embed_batch(batch: List[str]) -> list[DenseEmbedding]:
            async with semaphore:
                await self._rate_limiter.acquire()
                return await self._call_api(batch)

        results = await asyncio.gather(*[embed_batch(b) for b in batches])
        return [emb for batch in results for emb in batch]

    async def _call_api(self, batch: list[str]) -> list[DenseEmbedding]:
        """Call Mistral embeddings API."""

        def _sync_call() -> list[list[float]]:
            request = {"model": self._model_spec.api_model_name, "inputs": batch}
            try:
                response = self._client.embeddings.create(**request)
            except TypeError as exc:
                if "unexpected keyword argument 'inputs'" in str(exc):
                    request["input"] = request.pop("inputs")
                    response = self._client.embeddings.create(**request)
                else:
                    raise

            if not response.data:
                raise EmbedderProviderError("Mistral returned no embeddings")

            embeddings = [item.embedding for item in response.data]
            if len(embeddings) != len(batch):
                raise EmbedderProviderError(
                    f"Mistral returned {len(embeddings)} embeddings for {len(batch)} texts"
                )
            return embeddings

        raw = await run_in_thread_pool(_sync_call)
        return [DenseEmbedding(vector=v) for v in raw]

    async def close(self) -> None:
        """No-op — Mistral client doesn't need explicit cleanup."""
