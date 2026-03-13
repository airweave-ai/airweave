"""Gemini dense embedder satisfying DenseEmbedderProtocol.

Handles batching, concurrency, input validation, L2 normalization
for Matryoshka dimensions, purpose-aware task types, and error
translation. Callers pass text, get DenseEmbedding back, handle
errors themselves.
"""

import asyncio
import math

import httpx
from google import genai
from google.genai import errors

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
from airweave.domains.embedders.protocols import DenseEmbedderProtocol, EmbeddingPurpose
from airweave.domains.embedders.types import DenseEmbedding

_PROVIDER = "gemini"

# Gemini Embedding 2 advertises 8192 input tokens. We use a conservative
# character-based heuristic (~4 chars/token) since Gemini does not expose
# a public tokenizer.  This is deliberately generous — the API itself will
# reject truly over-limit inputs.
_MAX_CHARS_PER_TEXT: int = 40_000  # ~10K tokens at 4 chars/token


class GeminiDenseEmbedder(DenseEmbedderProtocol):
    """Gemini dense embedder satisfying DenseEmbedderProtocol.

    Handles batching, concurrency, input validation, L2 normalization
    for Matryoshka dimensions, purpose-aware task types, and error
    translation. Callers pass text, get DenseEmbedding back, handle
    errors themselves.
    """

    _MAX_TEXTS_PER_SUB_BATCH: int = 100
    _MAX_CONCURRENT_REQUESTS: int = 5
    _NATIVE_DIMENSIONS: int = 3072

    _PURPOSE_TO_TASK_TYPE: dict[EmbeddingPurpose, str] = {
        EmbeddingPurpose.DOCUMENT: "RETRIEVAL_DOCUMENT",
        EmbeddingPurpose.QUERY: "RETRIEVAL_QUERY",
    }

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimensions: int,
    ) -> None:
        """Initialize the Gemini dense embedder.

        Args:
            api_key: Google Gemini API key.
            model: Model name (e.g. "gemini-embedding-2-preview").
            dimensions: Matryoshka output dimensions (up to 3072).
        """
        self._model = model
        self._dimensions = dimensions
        self._client = genai.Client(api_key=api_key)
        self._semaphore = asyncio.Semaphore(self._MAX_CONCURRENT_REQUESTS)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def model_name(self) -> str:
        """The model identifier (e.g. "gemini-embedding-2-preview")."""
        return self._model

    @property
    def dimensions(self) -> int:
        """The output vector dimensionality."""
        return self._dimensions

    async def embed(
        self, text: str, *, purpose: EmbeddingPurpose = EmbeddingPurpose.DOCUMENT
    ) -> DenseEmbedding:
        """Embed a single text into a dense vector."""
        results = await self.embed_many([text], purpose=purpose)
        return results[0]

    async def embed_many(
        self, texts: list[str], *, purpose: EmbeddingPurpose = EmbeddingPurpose.DOCUMENT
    ) -> list[DenseEmbedding]:
        """Embed a batch of texts into dense vectors."""
        if not texts:
            return []

        self._validate_inputs(texts)

        sub_batches = [
            texts[i : i + self._MAX_TEXTS_PER_SUB_BATCH]
            for i in range(0, len(texts), self._MAX_TEXTS_PER_SUB_BATCH)
        ]

        tasks = [self._embed_sub_batch(batch, purpose) for batch in sub_batches]
        nested_results = await asyncio.gather(*tasks)

        return [embedding for batch_result in nested_results for embedding in batch_result]

    async def close(self) -> None:
        """Release held resources (best-effort, google-genai has no public close)."""
        try:
            await self._client.aio.live._api_client._http_client.aclose()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_inputs(self, texts: list[str]) -> None:
        """Validate all input texts.

        Raises:
            EmbedderInputError: If any text is empty/blank or exceeds
                the conservative character-length limit.
        """
        for i, text in enumerate(texts):
            if not text or not text.strip():
                raise EmbedderInputError(f"Text at index {i} is empty or blank")

            if len(text) > _MAX_CHARS_PER_TEXT:
                raise EmbedderInputError(
                    f"Text at index {i} has {len(text)} characters, "
                    f"exceeding the limit of {_MAX_CHARS_PER_TEXT}"
                )

    # ------------------------------------------------------------------
    # Batching
    # ------------------------------------------------------------------

    async def _embed_sub_batch(
        self, batch: list[str], purpose: EmbeddingPurpose
    ) -> list[DenseEmbedding]:
        """Embed a sub-batch with semaphore-controlled concurrency."""
        async with self._semaphore:
            return await self._embed_batch(batch, purpose)

    async def _embed_batch(
        self, batch: list[str], purpose: EmbeddingPurpose
    ) -> list[DenseEmbedding]:
        """Make a single API call and translate results/errors."""
        response = await self._call_api(batch, purpose)
        return self._validate_response(response, expected_count=len(batch))

    async def _call_api(self, batch: list[str], purpose: EmbeddingPurpose) -> object:
        """Call the Gemini embeddings API, translating provider exceptions.

        Raises:
            EmbedderAuthError: On authentication failure (401/403).
            EmbedderRateLimitError: On rate limit (HTTP 429).
            EmbedderTimeoutError: On request timeout.
            EmbedderConnectionError: On connection failure.
            EmbedderProviderError: On other API errors.
        """
        task_type = self._PURPOSE_TO_TASK_TYPE[purpose]

        try:
            config = {"output_dimensionality": self._dimensions}
            return await self._client.aio.models.embed_content(
                model=self._model,
                contents=batch,
                config={"task_type": task_type, **config},
            )
        except errors.ClientError as e:
            status = getattr(e, "code", None) or getattr(e, "status", None)
            if status in (401, 403):
                raise EmbedderAuthError(
                    f"Gemini authentication failed: {e}",
                    provider=_PROVIDER,
                ) from e
            if status == 429:
                raise EmbedderRateLimitError(
                    f"Gemini rate limit exceeded: {e}",
                    provider=_PROVIDER,
                ) from e
            raise EmbedderProviderError(
                f"Gemini API client error: {e}",
                provider=_PROVIDER,
                retryable=False,
            ) from e
        except errors.ServerError as e:
            raise EmbedderProviderError(
                f"Gemini API server error: {e}",
                provider=_PROVIDER,
                retryable=True,
            ) from e
        except (TimeoutError, httpx.TimeoutException) as e:
            raise EmbedderTimeoutError(
                f"Gemini request timed out: {e}",
                provider=_PROVIDER,
            ) from e
        except (ConnectionError, httpx.ConnectError) as e:
            raise EmbedderConnectionError(
                f"Gemini connection failed: {e}",
                provider=_PROVIDER,
            ) from e
        except httpx.RequestError as e:
            raise EmbedderConnectionError(
                f"Gemini transport error: {e}",
                provider=_PROVIDER,
            ) from e

    def _validate_response(self, response: object, *, expected_count: int) -> list[DenseEmbedding]:
        """Validate and convert the API response to DenseEmbedding objects.

        Applies L2 normalization when output dimensions < native 3072 to
        preserve cosine similarity after Matryoshka truncation.

        Raises:
            EmbedderResponseError: On count mismatch.
            EmbedderDimensionError: On dimension mismatch.
        """
        embeddings = response.embeddings  # type: ignore[attr-defined]

        if len(embeddings) != expected_count:
            raise EmbedderResponseError(
                f"Expected {expected_count} embeddings, got {len(embeddings)}"
            )

        needs_normalization = self._dimensions < self._NATIVE_DIMENSIONS

        results: list[DenseEmbedding] = []
        for emb in embeddings:
            vector = emb.values  # type: ignore[attr-defined]
            if len(vector) != self._dimensions:
                raise EmbedderDimensionError(
                    expected=self._dimensions,
                    actual=len(vector),
                )
            if needs_normalization:
                vector = self._l2_normalize(vector)
            results.append(DenseEmbedding(vector=vector))

        return results

    @staticmethod
    def _l2_normalize(vector: list[float]) -> list[float]:
        """L2-normalize a vector in-place (no numpy dependency)."""
        norm = math.sqrt(sum(x * x for x in vector))
        if norm == 0.0:
            return vector
        return [x / norm for x in vector]
