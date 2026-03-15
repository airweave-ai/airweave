"""Gemini dense embedder satisfying DenseEmbedderProtocol.

Handles batching, concurrency, input validation, L2 normalization
for Matryoshka dimensions, purpose-aware task types, multimodal file
embedding, and error translation. Callers pass text or file paths,
get DenseEmbedding back, handle errors themselves.
"""

import asyncio
import math
import os

import aiofiles
import httpx
from google import genai
from google.genai import errors
from google.genai.types import Blob, Part

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
from airweave.domains.embedders.protocols import EmbeddingPurpose
from airweave.domains.embedders.types import DenseEmbedding

_PROVIDER = "gemini"

# Gemini Embedding 2 advertises 8192 input tokens. We use a conservative
# character-based heuristic (~4 chars/token) since Gemini does not expose
# a public tokenizer.  This is deliberately generous — the API itself will
# reject truly over-limit inputs.
_MAX_CHARS_PER_TEXT: int = 40_000  # ~10K tokens at 4 chars/token

# ---------------------------------------------------------------------------
# Multimodal constants
# ---------------------------------------------------------------------------

_MULTIMODAL_MIME_TYPES: set[str] = {
    "image/png",
    "image/jpeg",
    "application/pdf",
    "audio/mpeg",
    "audio/wav",
    "video/mp4",
}


def _get_max_pdf_pages() -> int:
    """Read configurable PDF page limit from settings, fallback to 6."""
    try:
        from airweave.core.config import settings
        return settings.MULTIMODAL_PDF_MAX_PAGES
    except Exception:
        return 6


def _get_max_file_size_bytes() -> int:
    """Read configurable file size limit from settings, fallback to 20MB."""
    try:
        from airweave.core.config import settings
        return settings.MULTIMODAL_MAX_FILE_SIZE_MB * 1024 * 1024
    except Exception:
        return 20 * 1024 * 1024


class GeminiDenseEmbedder:
    """Gemini dense embedder satisfying DenseEmbedderProtocol + MultimodalDenseEmbedderProtocol.

    Handles batching, concurrency, input validation, L2 normalization
    for Matryoshka dimensions, purpose-aware task types, multimodal file
    embedding, and error translation.
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
    # Public interface — DenseEmbedderProtocol
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
        """Release held resources (closes the async HTTP transport)."""
        try:
            await self._client.aio.aclose()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Public interface — MultimodalDenseEmbedderProtocol
    # ------------------------------------------------------------------

    @property
    def supports_multimodal(self) -> bool:
        """Whether this embedder supports native file embedding."""
        return True

    @property
    def supported_mime_types(self) -> set[str]:
        """Set of MIME types this embedder can embed natively."""
        return _MULTIMODAL_MIME_TYPES

    async def embed_file(
        self,
        file_path: str,
        mime_type: str,
        *,
        purpose: EmbeddingPurpose = EmbeddingPurpose.DOCUMENT,
    ) -> DenseEmbedding:
        """Embed a file natively via the Gemini API.

        Reads the file from disk, sends it as inline_data to the embedding
        API, and returns a single DenseEmbedding. The file bytes are discarded
        after the API call to avoid memory amplification.

        Args:
            file_path: Path to the file on disk.
            mime_type: MIME type of the file.
            purpose: Whether this is a document or query embedding.

        Returns:
            A single DenseEmbedding for the file.

        Raises:
            EmbedderInputError: If the file is invalid.
        """
        self._validate_file_input(file_path, mime_type)
        file_bytes = await self._read_file_bytes(file_path)

        part = Part(inline_data=Blob(data=file_bytes, mime_type=mime_type))
        response = await self._call_multimodal_api(part, purpose)
        results = self._validate_response(response, expected_count=1)
        return results[0]

    # ------------------------------------------------------------------
    # Text validation
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
    # File validation
    # ------------------------------------------------------------------

    def _validate_file_input(self, file_path: str, mime_type: str) -> None:
        """Validate file input for multimodal embedding.

        Raises:
            EmbedderInputError: On unsupported MIME, missing file, size exceeded,
                or PDF page count exceeded.
        """
        if mime_type not in _MULTIMODAL_MIME_TYPES:
            raise EmbedderInputError(
                f"Unsupported MIME type for multimodal embedding: {mime_type}. "
                f"Supported: {sorted(_MULTIMODAL_MIME_TYPES)}"
            )

        if not os.path.isfile(file_path):
            raise EmbedderInputError(f"File not found: {file_path}")

        max_bytes = _get_max_file_size_bytes()
        file_size = os.path.getsize(file_path)
        if file_size > max_bytes:
            raise EmbedderInputError(
                f"File size {file_size} bytes exceeds limit of {max_bytes} bytes"
            )

        if file_size == 0:
            raise EmbedderInputError(f"File is empty: {file_path}")

        if mime_type == "application/pdf":
            self._validate_pdf_pages(file_path)

    def _validate_pdf_pages(self, file_path: str) -> None:
        """Check that a PDF has at most the configured max pages.

        Raises:
            EmbedderInputError: If the PDF exceeds the page limit.
        """
        import fitz  # PyMuPDF — already in pyproject.toml

        max_pages = _get_max_pdf_pages()

        try:
            with fitz.open(file_path) as doc:
                page_count = len(doc)
        except Exception as e:
            raise EmbedderInputError(f"Failed to read PDF: {e}") from e

        if page_count > max_pages:
            raise EmbedderInputError(
                f"PDF has {page_count} pages, exceeding the limit of {max_pages}"
            )

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    @staticmethod
    async def _read_file_bytes(file_path: str) -> bytes:
        """Read file contents asynchronously.

        Raises:
            EmbedderInputError: If the file cannot be read.
        """
        try:
            async with aiofiles.open(file_path, "rb") as f:
                return await f.read()
        except OSError as e:
            raise EmbedderInputError(f"Failed to read file {file_path}: {e}") from e

    # ------------------------------------------------------------------
    # Batching (text)
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

    # ------------------------------------------------------------------
    # API calls
    # ------------------------------------------------------------------

    async def _call_api(self, batch: list[str], purpose: EmbeddingPurpose) -> object:
        """Call the Gemini embeddings API for text, translating provider exceptions."""
        task_type = self._PURPOSE_TO_TASK_TYPE[purpose]

        try:
            config = {"output_dimensionality": self._dimensions}
            return await self._client.aio.models.embed_content(
                model=self._model,
                contents=batch,
                config={"task_type": task_type, **config},
            )
        except errors.ClientError as e:
            self._translate_client_error(e)
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

    async def _call_multimodal_api(
        self, part: Part, purpose: EmbeddingPurpose
    ) -> object:
        """Call the Gemini embeddings API for a file Part, translating provider exceptions."""
        task_type = self._PURPOSE_TO_TASK_TYPE[purpose]

        try:
            async with self._semaphore:
                return await self._client.aio.models.embed_content(
                    model=self._model,
                    contents=[part],
                    config={
                        "task_type": task_type,
                        "output_dimensionality": self._dimensions,
                    },
                )
        except errors.ClientError as e:
            self._translate_client_error(e)
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

    def _translate_client_error(self, e: errors.ClientError) -> None:
        """Translate a Gemini ClientError into domain exceptions.

        Always raises — never returns normally.
        """
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

    # ------------------------------------------------------------------
    # Response validation
    # ------------------------------------------------------------------

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
        """L2-normalize a vector, returning a new list (no numpy dependency)."""
        norm = math.sqrt(sum(x * x for x in vector))
        if norm == 0.0:
            return vector
        return [x / norm for x in vector]
