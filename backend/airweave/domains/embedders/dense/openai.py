"""OpenAI dense embedder satisfying DenseEmbedderProtocol.

Handles batching, concurrency, token validation, input/response
validation, and error translation. Callers pass text, get
DenseEmbedding back, handle errors themselves.
"""

import asyncio

import tiktoken
from openai import AsyncOpenAI

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

_PROVIDER = "openai"


class OpenAIDenseEmbedder(DenseEmbedderProtocol):
    """OpenAI dense embedder satisfying DenseEmbedderProtocol.

    Handles batching, concurrency, token validation, input/response
    validation, and error translation. Callers pass text, get
    DenseEmbedding back, handle errors themselves.
    """

    _MAX_TOKENS_PER_TEXT: int = 8192
    _MAX_TEXTS_PER_SUB_BATCH: int = 100
    _MAX_TOKENS_PER_REQUEST: int = 300_000
    _MAX_CONCURRENT_REQUESTS: int = 10
    _CLIENT_TIMEOUT: float = 1200.0
    _CLIENT_MAX_RETRIES: int = 2

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimensions: int,
    ) -> None:
        """Initialize the OpenAI dense embedder.

        Args:
            api_key: OpenAI API key.
            model: Model name (e.g. "text-embedding-3-large").
            dimensions: Matryoshka output dimensions.
        """
        self._model = model
        self._dimensions = dimensions
        self._client = AsyncOpenAI(
            api_key=api_key,
            timeout=self._CLIENT_TIMEOUT,
            max_retries=self._CLIENT_MAX_RETRIES,
        )
        self._encoder = tiktoken.get_encoding("cl100k_base")
        self._semaphore = asyncio.Semaphore(self._MAX_CONCURRENT_REQUESTS)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def model_name(self) -> str:
        """The model identifier (e.g. "text-embedding-3-large")."""
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

        token_counts = self._validate_inputs(texts)

        sub_batches = [
            (
                texts[i : i + self._MAX_TEXTS_PER_SUB_BATCH],
                token_counts[i : i + self._MAX_TEXTS_PER_SUB_BATCH],
            )
            for i in range(0, len(texts), self._MAX_TEXTS_PER_SUB_BATCH)
        ]

        tasks = [self._embed_sub_batch(batch, counts) for batch, counts in sub_batches]
        nested_results = await asyncio.gather(*tasks)

        return [embedding for batch_result in nested_results for embedding in batch_result]

    async def close(self) -> None:
        """Release held resources."""
        await self._client.close()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_inputs(self, texts: list[str]) -> list[int]:
        """Validate all input texts and return per-text token counts.

        Returns:
            List of token counts, one per input text.

        Raises:
            EmbedderInputError: If any text is empty/blank or exceeds the
                per-text token limit.
        """
        token_counts: list[int] = []
        for i, text in enumerate(texts):
            if not text or not text.strip():
                raise EmbedderInputError(f"Text at index {i} is empty or blank")

            token_count = len(self._encoder.encode(text, allowed_special="all"))
            if token_count > self._MAX_TOKENS_PER_TEXT:
                raise EmbedderInputError(
                    f"Text at index {i} has {token_count} tokens, "
                    f"exceeding the limit of {self._MAX_TOKENS_PER_TEXT}"
                )
            token_counts.append(token_count)
        return token_counts

    # ------------------------------------------------------------------
    # Batching
    # ------------------------------------------------------------------

    async def _embed_sub_batch(
        self, batch: list[str], token_counts: list[int]
    ) -> list[DenseEmbedding]:
        """Embed a sub-batch, splitting recursively if tokens exceed the limit."""
        total_tokens = sum(token_counts)

        if total_tokens > self._MAX_TOKENS_PER_REQUEST and len(batch) > 1:
            mid = len(batch) // 2
            left, right = await asyncio.gather(
                self._embed_sub_batch(batch[:mid], token_counts[:mid]),
                self._embed_sub_batch(batch[mid:], token_counts[mid:]),
            )
            return left + right

        async with self._semaphore:
            return await self._embed_batch(batch)

    async def _embed_batch(self, batch: list[str]) -> list[DenseEmbedding]:
        """Make a single API call and translate results/errors."""
        response = await self._call_api(batch)
        return self._validate_response(response, expected_count=len(batch))

    async def _call_api(self, batch: list[str]) -> object:
        """Call the OpenAI embeddings API, translating provider exceptions.

        Raises:
            EmbedderAuthError: On authentication failure.
            EmbedderRateLimitError: On rate limit (HTTP 429).
            EmbedderTimeoutError: On request timeout.
            EmbedderConnectionError: On connection failure.
            EmbedderProviderError: On other API errors.
        """
        import openai

        try:
            return await self._client.embeddings.create(
                input=batch,
                model=self._model,
                dimensions=self._dimensions,
                encoding_format="float",
            )
        except openai.AuthenticationError as e:
            raise EmbedderAuthError(
                f"OpenAI authentication failed: {e}",
                provider=_PROVIDER,
            ) from e
        except openai.RateLimitError as e:
            retry_after = self._parse_retry_after(e)
            raise EmbedderRateLimitError(
                f"OpenAI rate limit exceeded: {e}",
                provider=_PROVIDER,
                retry_after=retry_after,
            ) from e
        except openai.APITimeoutError as e:
            raise EmbedderTimeoutError(
                f"OpenAI request timed out: {e}",
                provider=_PROVIDER,
            ) from e
        except openai.APIConnectionError as e:
            raise EmbedderConnectionError(
                f"OpenAI connection failed: {e}",
                provider=_PROVIDER,
            ) from e
        except openai.APIStatusError as e:
            raise EmbedderProviderError(
                f"OpenAI API error (status {e.status_code}): {e}",
                provider=_PROVIDER,
                retryable=e.status_code >= 500,
            ) from e

    @staticmethod
    def _parse_retry_after(exc: Exception) -> float | None:
        """Extract retry-after seconds from a RateLimitError response."""
        if hasattr(exc, "response") and exc.response is not None:
            retry_header = exc.response.headers.get("retry-after")
            if retry_header is not None:
                try:
                    return float(retry_header)
                except (ValueError, TypeError):
                    pass
        return None

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
