"""Local dense embedder satisfying DenseEmbedderProtocol.

Calls a text2vec-transformers inference container over HTTP.
Handles batching, concurrency, input/response validation, and
error translation. Callers pass text, get DenseEmbedding back,
handle errors themselves.
"""

import asyncio

import httpx

from airweave.domains.embedders.exceptions import (
    EmbedderConnectionError,
    EmbedderDimensionError,
    EmbedderInputError,
    EmbedderProviderError,
    EmbedderResponseError,
    EmbedderTimeoutError,
)
from airweave.domains.embedders.types import DenseEmbedding

_PROVIDER = "local"


class LocalDenseEmbedder:
    """Local dense embedder satisfying DenseEmbedderProtocol.

    Calls a text2vec-transformers inference container over HTTP.
    Handles batching, concurrency, input/response validation, and
    error translation. Callers pass text, get DenseEmbedding back,
    handle errors themselves.
    """

    _MAX_BATCH_SIZE: int = 64
    _MAX_CONCURRENT_REQUESTS: int = 10
    _CLIENT_TIMEOUT: float = 60.0

    def __init__(
        self,
        *,
        inference_url: str,
        dimensions: int,
    ) -> None:
        """Initialize the local dense embedder.

        Args:
            inference_url: Base URL of the text2vec inference container.
            dimensions: Expected output dimensions (validated on response).
        """
        self._inference_url = inference_url
        self._dimensions = dimensions
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._CLIENT_TIMEOUT),
            limits=httpx.Limits(max_connections=self._MAX_CONCURRENT_REQUESTS * 2),
        )
        self._semaphore = asyncio.Semaphore(self._MAX_CONCURRENT_REQUESTS)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def model_name(self) -> str:
        """The model identifier."""
        return "local"

    @property
    def dimensions(self) -> int:
        """The output vector dimensionality."""
        return self._dimensions

    async def embed(self, text: str) -> DenseEmbedding:
        """Embed a single text into a dense vector."""
        results = await self.embed_many([text])
        return results[0]

    async def embed_many(self, texts: list[str]) -> list[DenseEmbedding]:
        """Embed a batch of texts into dense vectors."""
        if not texts:
            return []

        self._validate_inputs(texts)

        sub_batches = [
            texts[i : i + self._MAX_BATCH_SIZE] for i in range(0, len(texts), self._MAX_BATCH_SIZE)
        ]

        tasks = [self._embed_sub_batch(batch) for batch in sub_batches]
        nested_results = await asyncio.gather(*tasks)

        return [embedding for batch_result in nested_results for embedding in batch_result]

    async def close(self) -> None:
        """Release held resources."""
        await self._client.aclose()

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
    # Batching
    # ------------------------------------------------------------------

    async def _embed_sub_batch(self, batch: list[str]) -> list[DenseEmbedding]:
        """Embed a sub-batch by fanning out individual HTTP calls."""
        tasks = [self._embed_single(text) for text in batch]
        return list(await asyncio.gather(*tasks))

    async def _embed_single(self, text: str) -> DenseEmbedding:
        """Make a single HTTP call to the inference container.

        Raises:
            EmbedderTimeoutError: On request timeout.
            EmbedderConnectionError: On connection failure.
            EmbedderProviderError: On HTTP error response.
            EmbedderResponseError: On missing 'vector' key.
            EmbedderDimensionError: On dimension mismatch.
        """
        async with self._semaphore:
            try:
                response = await self._client.post(
                    f"{self._inference_url}/vectors",
                    json={"text": text},
                )
                response.raise_for_status()
                data = response.json()
            except httpx.TimeoutException as e:
                raise EmbedderTimeoutError(
                    f"Local embedding request timed out: {e}",
                    provider=_PROVIDER,
                ) from e
            except httpx.ConnectError as e:
                raise EmbedderConnectionError(
                    f"Local embedding connection failed: {e}",
                    provider=_PROVIDER,
                ) from e
            except httpx.HTTPStatusError as e:
                raise EmbedderProviderError(
                    f"Local embedding service error (status {e.response.status_code}): "
                    f"{e.response.text}",
                    provider=_PROVIDER,
                    retryable=e.response.status_code >= 500,
                ) from e
            except httpx.RequestError as e:
                raise EmbedderConnectionError(
                    f"Local embedding connection failed: {e}",
                    provider=_PROVIDER,
                ) from e

            if "vector" not in data:
                raise EmbedderResponseError(
                    "Invalid response from local embedding service: missing 'vector' key"
                )

            vector = data["vector"]
            if len(vector) != self._dimensions:
                raise EmbedderDimensionError(
                    expected=self._dimensions,
                    actual=len(vector),
                )

            return DenseEmbedding(vector=vector)
