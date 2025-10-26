"""OpenAI dense embedder using text-embedding-3-large."""

from typing import List

import tiktoken
from openai import AsyncOpenAI

from airweave.core.config import settings
from airweave.platform.rate_limiters.openai import OpenAIRateLimiter
from airweave.platform.sync.context import SyncContext
from airweave.platform.sync.exceptions import SyncFailureError

from ._base import BaseEmbedder


class DenseEmbedder(BaseEmbedder):
    """Singleton dense embedder using OpenAI text-embedding-3-large (3072 dims).

    Features:
    - Singleton shared across all syncs in pod
    - Batch processing with OpenAI limits (2048 texts/request, 300K tokens/request)
    - 5 concurrent requests max
    - Rate limiting with OpenAIRateLimiter singleton
    - Automatic retry on transient errors (via AsyncOpenAI client)
    - Fail-fast on any API errors (no silent failures)
    """

    MODEL_NAME = "text-embedding-3-large"
    VECTOR_DIMENSIONS = 3072
    MAX_TOKENS_PER_TEXT = 8192  # OpenAI limit per text
    MAX_BATCH_SIZE = 2048  # OpenAI limit per request
    MAX_TOKENS_PER_REQUEST = 300000  # OpenAI limit
    MAX_CONCURRENT_REQUESTS = 5

    def __init__(self):
        """Initialize OpenAI embedder (once per pod)."""
        if self._initialized:
            return

        if not settings.OPENAI_API_KEY:
            raise SyncFailureError("OPENAI_API_KEY required for dense embeddings")

        self._client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=1200.0,  # 20 min timeout for high concurrency
            max_retries=2,
        )
        self._rate_limiter = OpenAIRateLimiter()  # Singleton
        self._tokenizer = tiktoken.get_encoding("cl100k_base")
        self._initialized = True

    async def embed_many(self, texts: List[str], sync_context: SyncContext) -> List[List[float]]:
        """Embed batch of texts using OpenAI text-embedding-3-large.

        Returns exactly len(texts) vectors (3072-dim each).
        Raises SyncFailureError on ANY error (no silent failures).

        Args:
            texts: List of text strings to embed (must not be empty)
            sync_context: Sync context with logger

        Returns:
            List of 3072-dimensional embedding vectors

        Raises:
            SyncFailureError: On any error (empty texts, API failures, etc.)
        """
        if not texts:
            return []

        # Validate no empty texts
        for i, text in enumerate(texts):
            if not text or not text.strip():
                raise SyncFailureError(
                    f"PROGRAMMING ERROR: Empty text at index {i}. "
                    f"Textual representation must be set before embedding."
                )

        # Count tokens for the entire batch
        total_tokens = sum(len(self._tokenizer.encode(text)) for text in texts)

        sync_context.logger.debug(f"Embedding {len(texts)} texts with {total_tokens} total tokens")

        # Check if we need to split due to token limit
        # Batch size is typically 64, so even if all texts are 8192 tokens (unlikely),
        # one split in half is sufficient: 64*8192=524288 → 524288/2=262144 < 300K
        if total_tokens > self.MAX_TOKENS_PER_REQUEST:
            sync_context.logger.debug(
                f"Batch exceeds {self.MAX_TOKENS_PER_REQUEST} tokens, splitting in half"
            )
            mid = len(texts) // 2
            first_half = await self.embed_many(texts[:mid], sync_context)
            second_half = await self.embed_many(texts[mid:], sync_context)
            return first_half + second_half

        # Process single request with rate limiting
        embeddings = await self._embed_batch(texts, sync_context)

        # Validate result count matches input count
        if len(embeddings) != len(texts):
            raise SyncFailureError(
                f"PROGRAMMING ERROR: Got {len(embeddings)} embeddings for {len(texts)} texts"
            )

        return embeddings

    async def _embed_batch(self, batch: List[str], sync_context: SyncContext) -> List[List[float]]:
        """Embed single batch with rate limiting and error handling.

        Args:
            batch: List of texts to embed (must fit in one OpenAI request)
            sync_context: Sync context with logger

        Returns:
            List of embedding vectors

        Raises:
            SyncFailureError: On any API error
        """
        try:
            # Rate limit (singleton shared across pod)
            await self._rate_limiter.acquire()

            # Call OpenAI API
            response = await self._client.embeddings.create(
                input=batch,
                model=self.MODEL_NAME,
                encoding_format="float",
            )

            # Extract embeddings
            embeddings = [e.embedding for e in response.data]

            # Validate response
            if len(embeddings) != len(batch):
                raise SyncFailureError(
                    f"OpenAI returned {len(embeddings)} embeddings for {len(batch)} texts"
                )

            # Validate dimensions
            if embeddings and len(embeddings[0]) != self.VECTOR_DIMENSIONS:
                raise SyncFailureError(
                    f"OpenAI returned {len(embeddings[0])}-dim vectors, "
                    f"expected {self.VECTOR_DIMENSIONS}"
                )

            return embeddings

        except SyncFailureError:
            # Re-raise SyncFailureError as-is
            raise
        except Exception as e:
            error_msg = str(e).lower()

            # Check for token limit error (should be impossible if chunker worked)
            if "maximum context length" in error_msg or "max_tokens" in error_msg:
                raise SyncFailureError(
                    f"Token limit exceeded during embedding - chunker failed to enforce limits: {e}"
                )

            # Any other error is also fatal
            sync_context.logger.error(f"OpenAI embedding API error: {e}")
            raise SyncFailureError(f"OpenAI embedding failed: {e}")
