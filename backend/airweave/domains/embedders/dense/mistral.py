"""Mistral dense embedder satisfying DenseEmbedderProtocol.

Handles batching, concurrency, token validation, input/response
validation, and error translation. Callers pass text, get
DenseEmbedding back, handle errors themselves.
"""

import asyncio

from mistralai import Mistral

from airweave.domains.embedders.exceptions import (
    EmbedderAuthError,
    EmbedderConnectionError,
    EmbedderDimensionError,
    EmbedderInputError,
    EmbedderProviderError,
    EmbedderRateLimitError,
    EmbedderResponseError,
    EmbedderTimeoutError,
)
from airweave.domains.embedders.protocols import DenseEmbedderProtocol
from airweave.domains.embedders.types import DenseEmbedding
from airweave.platform.tokenizers import get_tokenizer

_PROVIDER = "mistral"


class MistralDenseEmbedder(DenseEmbedderProtocol):
    """Mistral dense embedder satisfying DenseEmbedderProtocol.

    Handles batching, concurrency, token validation, input/response
    validation, and error translation. Callers pass text, get
    DenseEmbedding back, handle errors themselves.
    """

    _MAX_BATCH_SIZE: int = 128
    _MAX_CONCURRENT_REQUESTS: int = 5
    _MAX_TOKENS_PER_TEXT: int = 8000
    _MAX_TOKENS_PER_REQUEST: int = 8000

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimensions: int,
    ) -> None:
        """Initialize the Mistral dense embedder.

        Args:
            api_key: Mistral API key.
            model: Model name (e.g. "mistral-embed").
            dimensions: Expected output dimensions (validated on response only).
        """
        self._model = model
        self._dimensions = dimensions
        self._client = Mistral(api_key=api_key)
        self._tokenizer = get_tokenizer(model)
        self._semaphore = asyncio.Semaphore(self._MAX_CONCURRENT_REQUESTS)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def model_name(self) -> str:
        """The model identifier (e.g. "mistral-embed")."""
        return self._model

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
        await self._client.close_async()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_inputs(self, texts: list[str]) -> None:
        """Validate all input texts.

        Raises:
            EmbedderInputError: If any text is empty/blank or exceeds the
                per-text token limit.
        """
        for i, text in enumerate(texts):
            if not text or not text.strip():
                raise EmbedderInputError(f"Text at index {i} is empty or blank")

            token_count = self._tokenizer.count_tokens(text)
            if token_count > self._MAX_TOKENS_PER_TEXT:
                raise EmbedderInputError(
                    f"Text at index {i} has {token_count} tokens, "
                    f"exceeding the limit of {self._MAX_TOKENS_PER_TEXT}"
                )

    # ------------------------------------------------------------------
    # Batching
    # ------------------------------------------------------------------

    async def _embed_sub_batch(self, batch: list[str]) -> list[DenseEmbedding]:
        """Embed a sub-batch, splitting recursively if tokens exceed the limit."""
        total_tokens = sum(self._tokenizer.count_tokens(text) for text in batch)

        if total_tokens > self._MAX_TOKENS_PER_REQUEST and len(batch) > 1:
            mid = len(batch) // 2
            left, right = await asyncio.gather(
                self._embed_sub_batch(batch[:mid]),
                self._embed_sub_batch(batch[mid:]),
            )
            return left + right

        async with self._semaphore:
            return await self._embed_batch(batch)

    async def _embed_batch(self, batch: list[str]) -> list[DenseEmbedding]:
        """Make a single API call and translate results/errors."""
        response = await self._call_api(batch)
        return self._validate_response(response, expected_count=len(batch))

    async def _call_api(self, batch: list[str]) -> object:
        """Call the Mistral embeddings API, translating provider exceptions.

        Raises:
            EmbedderAuthError: On authentication failure (HTTP 401).
            EmbedderRateLimitError: On rate limit (HTTP 429).
            EmbedderTimeoutError: On request timeout.
            EmbedderConnectionError: On connection failure.
            EmbedderProviderError: On other API errors.
        """
        import httpx
        from mistralai.models import SDKError

        try:
            return await self._create_embeddings(batch)
        except SDKError as e:
            status = getattr(e, "status_code", None)
            if status == 401:
                raise EmbedderAuthError(
                    f"Mistral authentication failed: {e}",
                    provider=_PROVIDER,
                ) from e
            if status == 429:
                raise EmbedderRateLimitError(
                    f"Mistral rate limit exceeded: {e}",
                    provider=_PROVIDER,
                ) from e
            if status is not None and status >= 500:
                raise EmbedderProviderError(
                    f"Mistral API error (status {status}): {e}",
                    provider=_PROVIDER,
                    retryable=True,
                ) from e
            raise EmbedderProviderError(
                f"Mistral API error: {e}",
                provider=_PROVIDER,
                retryable=False,
            ) from e
        except httpx.TimeoutException as e:
            raise EmbedderTimeoutError(
                f"Mistral request timed out: {e}",
                provider=_PROVIDER,
            ) from e
        except httpx.ConnectError as e:
            raise EmbedderConnectionError(
                f"Mistral connection failed: {e}",
                provider=_PROVIDER,
            ) from e
        except httpx.RequestError as e:
            raise EmbedderConnectionError(
                f"Mistral request failed: {e}",
                provider=_PROVIDER,
            ) from e

    async def _create_embeddings(self, batch: list[str]) -> object:
        """Call the Mistral SDK, falling back from ``inputs`` to ``input``."""
        try:
            return await self._client.embeddings.create_async(
                model=self._model,
                inputs=batch,
            )
        except TypeError as exc:
            if "unexpected keyword argument 'inputs'" in str(exc):
                return await self._client.embeddings.create_async(
                    model=self._model,
                    input=batch,
                )
            raise

    def _validate_response(self, response: object, *, expected_count: int) -> list[DenseEmbedding]:
        """Validate and convert the API response to DenseEmbedding objects.

        Raises:
            EmbedderResponseError: On count mismatch.
            EmbedderDimensionError: On dimension mismatch.
        """
        embeddings = response.data  # type: ignore[attr-defined]

        if len(embeddings) != expected_count:
            raise EmbedderResponseError(
                f"Expected {expected_count} embeddings, got {len(embeddings)}"
            )

        results: list[DenseEmbedding] = []
        for emb in embeddings:
            if len(emb.embedding) != self._dimensions:
                raise EmbedderDimensionError(
                    expected=self._dimensions,
                    actual=len(emb.embedding),
                )
            results.append(DenseEmbedding(vector=emb.embedding))

        return results
