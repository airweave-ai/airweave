"""Local dense embedder using text2vec-transformers container.

Uses the semitechnologies/transformers-inference container running locally
or in a sidecar. Default model is all-MiniLM-L6-v2 (384 dimensions).
"""

import asyncio
from typing import List

import httpx

from airweave.core.logging import logger
from airweave.domains.embedders.dense.registry import DenseModelSpec
from airweave.domains.embedders.exceptions import EmbedderProviderError
from airweave.domains.embedders.schemas import DenseEmbedding


class LocalDenseEmbedder:
    """Local dense embedder using text2vec-transformers inference service."""

    MAX_CONCURRENT_REQUESTS = 10
    MAX_BATCH_SIZE = 64
    REQUEST_TIMEOUT = 60.0

    def __init__(
        self,
        model_spec: DenseModelSpec,
        target_dimensions: int,
        inference_url: str | None = None,
    ) -> None:
        """Initialize local embedder.

        Args:
            model_spec: Model specification from registry.
            target_dimensions: Expected vector dimensions.
            inference_url: URL of the text2vec inference service.
                Falls back to settings if not provided.
        """
        self._model_spec = model_spec
        self._target_dimensions = target_dimensions

        if inference_url is None:
            from airweave.core.config import settings

            inference_url = settings.TEXT2VEC_INFERENCE_URL

        self._inference_url = inference_url
        if not self._inference_url:
            raise EmbedderProviderError(
                "TEXT2VEC_INFERENCE_URL required for local embeddings. "
                "Start the text2vec-transformers container or set an API key."
            )

        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.REQUEST_TIMEOUT),
            limits=httpx.Limits(max_connections=self.MAX_CONCURRENT_REQUESTS * 2),
        )

    @property
    def vector_size(self) -> int:
        """Return the output dimension of this embedder."""
        return self._target_dimensions

    async def embed(self, text: str) -> DenseEmbedding:
        """Embed a single text."""
        results = await self.embed_many([text])
        return results[0]

    async def embed_many(self, texts: list[str]) -> list[DenseEmbedding]:
        """Embed batch of texts using local inference service."""
        if not texts:
            return []

        for i, text in enumerate(texts):
            if not text or not text.strip():
                raise EmbedderProviderError(
                    f"Empty text at index {i}. "
                    f"Textual representation must be set before embedding."
                )

        logger.debug(
            f"[LocalEmbed] Embedding {len(texts)} texts "
            f"-> {self._target_dimensions}-dim vectors"
        )

        if len(texts) > self.MAX_BATCH_SIZE:
            return await self._embed_batched(texts)

        return await self._embed_batch(texts)

    async def _embed_batched(self, texts: list[str]) -> list[DenseEmbedding]:
        """Embed texts in concurrent batches."""
        batches = [
            texts[i : i + self.MAX_BATCH_SIZE]
            for i in range(0, len(texts), self.MAX_BATCH_SIZE)
        ]

        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)

        async def embed_with_limit(batch: List[str]) -> list[DenseEmbedding]:
            async with semaphore:
                return await self._embed_batch(batch)

        results = await asyncio.gather(
            *[embed_with_limit(batch) for batch in batches]
        )
        return [emb for batch_result in results for emb in batch_result]

    async def _embed_batch(self, batch: list[str]) -> list[DenseEmbedding]:
        """Embed a single batch by calling inference service for each text."""

        async def embed_single(text: str) -> DenseEmbedding:
            try:
                response = await self._client.post(
                    f"{self._inference_url}/vectors",
                    json={"text": text},
                )
                response.raise_for_status()
                data = response.json()
                vector = data["vector"]

                if len(vector) != self._target_dimensions:
                    raise EmbedderProviderError(
                        f"Local model returned {len(vector)}-dim vector, "
                        f"expected {self._target_dimensions}"
                    )

                return DenseEmbedding(vector=vector)
            except httpx.HTTPStatusError as e:
                raise EmbedderProviderError(
                    f"Local embedding service error: "
                    f"{e.response.status_code} - {e.response.text}"
                )
            except httpx.RequestError as e:
                raise EmbedderProviderError(
                    f"Local embedding service unavailable at "
                    f"{self._inference_url}: {e}"
                )
            except KeyError:
                raise EmbedderProviderError(
                    "Invalid response from local embedding service: "
                    "missing 'vector' key"
                )

        embeddings = await asyncio.gather(*[embed_single(text) for text in batch])
        return list(embeddings)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
