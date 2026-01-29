"""Local dense embedder using text2vec-transformers container.

Uses the semitechnologies/transformers-inference container running locally
or in a sidecar. Default model is all-MiniLM-L6-v2 (384 dimensions).
"""

import asyncio
import time
from typing import TYPE_CHECKING, List, Optional, Union

import httpx

from airweave.core.config import settings
from airweave.core.logging import ContextualLogger
from airweave.core.logging import logger as default_logger
from airweave.platform.sync.exceptions import SyncFailureError

from ._base import BaseEmbedder

if TYPE_CHECKING:
    from airweave.platform.contexts import SyncContext


class LocalDenseEmbedder(BaseEmbedder):
    """Local dense embedder using text2vec-transformers inference service.

    Features:
    - No API keys required - runs locally via Docker
    - Default: all-MiniLM-L6-v2 (384 dimensions)
    - Concurrent requests with configurable limits
    - Automatic batching for efficiency
    """

    # Configuration
    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    VECTOR_DIMENSIONS = 384
    MAX_CONCURRENT_REQUESTS = 10
    MAX_BATCH_SIZE = 64  # Local service can handle smaller batches faster
    REQUEST_TIMEOUT = 60.0  # Local inference is fast

    def __new__(cls, vector_size: int = None, model_name: str = None):
        """Create fresh instance (override singleton from BaseEmbedder)."""
        return object.__new__(cls)

    def __init__(self, vector_size: int = None, model_name: str = None):
        """Initialize local embedder.

        Args:
            vector_size: Expected vector dimensions (default: 384)
            model_name: Model name for logging (default: all-MiniLM-L6-v2)
        """
        self._inference_url = settings.TEXT2VEC_INFERENCE_URL
        if not self._inference_url:
            raise SyncFailureError(
                "TEXT2VEC_INFERENCE_URL required for local embeddings. "
                "Start the text2vec-transformers container or set an API key."
            )

        self.VECTOR_DIMENSIONS = vector_size or 384
        self.MODEL_NAME = model_name or "sentence-transformers/all-MiniLM-L6-v2"

        # Create async HTTP client
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.REQUEST_TIMEOUT),
            limits=httpx.Limits(max_connections=self.MAX_CONCURRENT_REQUESTS * 2),
        )

    async def embed_many(
        self,
        texts: List[str],
        context: Union["SyncContext", ContextualLogger, None] = None,
        dimensions: Optional[int] = None,
    ) -> List[List[float]]:
        """Embed batch of texts using local inference service.

        Args:
            texts: List of text strings to embed
            context: Sync context or logger for debug output
            dimensions: Ignored (local model has fixed dimensions)

        Returns:
            List of embedding vectors

        Raises:
            SyncFailureError: On any error
        """
        # Extract logger
        if context is None:
            logger = default_logger
        elif isinstance(context, ContextualLogger):
            logger = context
        else:
            logger = context.logger

        if not texts:
            return []

        # Validate no empty texts
        for i, text in enumerate(texts):
            if not text or not text.strip():
                raise SyncFailureError(
                    f"Empty text at index {i}. "
                    f"Textual representation must be set before embedding."
                )

        logger.debug(
            f"[LocalEmbed] Embedding {len(texts)} texts -> {self.VECTOR_DIMENSIONS}-dim vectors"
        )

        # Process in batches with concurrency
        if len(texts) > self.MAX_BATCH_SIZE:
            return await self._embed_batched(texts, logger)

        # Single batch
        return await self._embed_batch(texts, logger)

    async def _embed_batched(
        self, texts: List[str], logger: ContextualLogger
    ) -> List[List[float]]:
        """Embed texts in concurrent batches."""
        batches = [
            texts[i : i + self.MAX_BATCH_SIZE]
            for i in range(0, len(texts), self.MAX_BATCH_SIZE)
        ]

        logger.debug(
            f"[LocalEmbed] Processing {len(batches)} batches "
            f"(max {self.MAX_CONCURRENT_REQUESTS} concurrent)"
        )

        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)
        start_time = time.monotonic()

        async def embed_with_limit(batch_idx: int, batch: List[str]) -> List[List[float]]:
            async with semaphore:
                return await self._embed_batch(batch, logger, batch_idx, len(batches))

        results = await asyncio.gather(
            *[embed_with_limit(i, batch) for i, batch in enumerate(batches)]
        )

        elapsed = time.monotonic() - start_time
        logger.debug(f"[LocalEmbed] All {len(batches)} batches completed in {elapsed:.2f}s")

        # Flatten results
        return [emb for batch_result in results for emb in batch_result]

    async def _embed_batch(
        self,
        batch: List[str],
        logger: ContextualLogger,
        batch_idx: int = 0,
        total_batches: int = 1,
    ) -> List[List[float]]:
        """Embed a single batch by calling inference service for each text.

        The text2vec-transformers service processes one text at a time,
        so we parallelize within the batch.
        """
        start_time = time.monotonic()

        # Process texts in parallel within batch
        async def embed_single(text: str) -> List[float]:
            try:
                response = await self._client.post(
                    f"{self._inference_url}/vectors",
                    json={"text": text},
                )
                response.raise_for_status()
                data = response.json()
                return data["vector"]
            except httpx.HTTPStatusError as e:
                raise SyncFailureError(
                    f"Local embedding service error: {e.response.status_code} - {e.response.text}"
                )
            except httpx.RequestError as e:
                raise SyncFailureError(
                    f"Local embedding service unavailable at {self._inference_url}: {e}"
                )
            except KeyError:
                raise SyncFailureError(
                    "Invalid response from local embedding service: missing 'vector' key"
                )

        embeddings = await asyncio.gather(*[embed_single(text) for text in batch])

        elapsed = time.monotonic() - start_time
        if elapsed > 1.0 or total_batches > 1:
            logger.debug(
                f"[LocalEmbed] Batch {batch_idx + 1}/{total_batches} "
                f"({len(batch)} texts) completed in {elapsed:.2f}s"
            )

        # Validate dimensions
        for emb in embeddings:
            if len(emb) != self.VECTOR_DIMENSIONS:
                raise SyncFailureError(
                    f"Local model returned {len(emb)}-dim vector, "
                    f"expected {self.VECTOR_DIMENSIONS}"
                )

        return list(embeddings)

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
