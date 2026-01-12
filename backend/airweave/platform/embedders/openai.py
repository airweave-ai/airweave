"""OpenAI dense embedder using text-embedding-3-large.

Supports Matryoshka embeddings via explicit dimension parameter for flexible
vector sizes (e.g., 768 for ranking, 96 for ANN search).
"""

import asyncio
import time
from typing import TYPE_CHECKING, List, Optional, Union

import tiktoken
from openai import AsyncOpenAI

from airweave.core.config import settings
from airweave.core.logging import ContextualLogger
from airweave.core.logging import logger as default_logger
from airweave.platform.rate_limiters.openai import OpenAIRateLimiter
from airweave.platform.sync.exceptions import SyncFailureError

from ._base import BaseEmbedder

if TYPE_CHECKING:
    from airweave.platform.contexts import SyncContext


class DenseEmbedder(BaseEmbedder):
    """OpenAI dense embedder with dynamic model selection (non-singleton).

    IMPORTANT: No longer a singleton! Each collection may use different embedding models,
    so we create fresh instances with the correct model for each sync/search operation.

    Features:
    - Dynamic model selection based on vector_size (3072 or 1536)
    - Batch processing with OpenAI limits (2048 texts/request, 300K tokens/request)
    - 10 concurrent requests max (safe with 6 pods at Tier 4: 10,000 RPM)
    - Rate limiting with OpenAIRateLimiter singleton (shared across instances)
    - Automatic retry on transient errors (via AsyncOpenAI client)
    - Fail-fast on any API errors (no silent failures)
    """

    MAX_TOKENS_PER_TEXT = 8192  # OpenAI limit per text
    MAX_BATCH_SIZE = 2048  # OpenAI limit per request
    MAX_TOKENS_PER_REQUEST = 300000  # OpenAI limit
    MAX_CONCURRENT_REQUESTS = 10  # Concurrent API requests per embedder instance

    def __new__(cls, vector_size: int = None):
        """Override singleton pattern from BaseEmbedder - create fresh instances."""
        return object.__new__(cls)

    def __init__(self, vector_size: int = None):
        """Initialize OpenAI embedder for specific vector dimensions.

        Args:
            vector_size: Vector dimensions to determine model:
                - 3072: text-embedding-3-large
                - 1536: text-embedding-3-small
                - None: defaults to 3072 (large model)
        """
        if not settings.OPENAI_API_KEY:
            raise SyncFailureError("OPENAI_API_KEY required for dense embeddings")

        # Fail-fast: vector_size should always be provided from collection
        # Only allow None for backward compatibility, but warn
        if vector_size is None:
            # Fallback to large model but this shouldn't happen
            self.MODEL_NAME = "text-embedding-3-large"
            self.VECTOR_DIMENSIONS = 3072
        else:
            # Select model and dimensions based on vector_size
            from airweave.platform.destinations.collection_strategy import (
                get_openai_embedding_model_for_vector_size,
            )

            self.MODEL_NAME = get_openai_embedding_model_for_vector_size(vector_size)
            self.VECTOR_DIMENSIONS = vector_size

        # Create fresh client instance
        self._client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=1200.0,  # 20 min timeout for high concurrency
            max_retries=2,
        )
        self._rate_limiter = OpenAIRateLimiter()  # This singleton is still OK (shared rate limit)
        self._tokenizer = tiktoken.get_encoding("cl100k_base")

    async def embed_many(
        self,
        texts: List[str],
        context: Union["SyncContext", ContextualLogger, None] = None,
        dimensions: Optional[int] = None,
    ) -> List[List[float]]:
        """Embed batch of texts using OpenAI text-embedding-3 models.

        Supports Matryoshka embeddings via explicit dimension parameter.
        OpenAI's text-embedding-3-* models support native dimension reduction.

        Args:
            texts: List of text strings to embed (must not be empty)
            context: Either a SyncContext (has .logger), a ContextualLogger, or None.
                    Used for debug logging only.
            dimensions: Optional dimension override for Matryoshka truncation.
                       If None, uses self.VECTOR_DIMENSIONS (model default).
                       Examples: 768 for ranking, 96 for ANN search.

        Returns:
            List of embedding vectors with specified dimensions

        Raises:
            SyncFailureError: On any error (empty texts, API failures, etc.)
        """
        # Extract logger from context (SyncContext has .logger, ContextualLogger is a logger)
        if context is None:
            logger = default_logger
        elif hasattr(context, "logger"):
            logger = context.logger  # SyncContext
        else:
            logger = context  # ContextualLogger directly

        # Use explicit dimensions if provided, else model default
        output_dims = dimensions or self.VECTOR_DIMENSIONS

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
        # Use allowed_special="all" to handle special tokens like <|endoftext|>
        # that may appear in user content
        total_tokens = sum(
            len(self._tokenizer.encode(text, allowed_special="all")) for text in texts
        )

        logger.debug(
            f"Embedding {len(texts)} texts with {total_tokens} tokens -> {output_dims}-dim vectors"
        )

        # Split into smaller batches and process concurrently
        # Max 100 texts per sub-batch to stay under 300K token limit
        # (100 texts × 2000 avg tokens = 200K tokens, safely under 300K)
        MAX_TEXTS_PER_SUBBATCH = 100

        if len(texts) > MAX_TEXTS_PER_SUBBATCH:
            # Create sub-batches
            sub_batches = [
                texts[i : i + MAX_TEXTS_PER_SUBBATCH]
                for i in range(0, len(texts), MAX_TEXTS_PER_SUBBATCH)
            ]

            logger.debug(
                f"[EMBED] Starting {len(sub_batches)} sub-batches "
                f"(max {self.MAX_CONCURRENT_REQUESTS} concurrent)"
            )

            # Process sub-batches concurrently with semaphore limit
            semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)
            active_count = 0
            active_lock = asyncio.Lock()
            batch_start_time = time.monotonic()

            async def embed_with_semaphore(
                batch_idx: int, sub_batch: List[str]
            ) -> List[List[float]]:
                nonlocal active_count
                wait_start = time.monotonic()

                async with semaphore:
                    async with active_lock:
                        active_count += 1
                        current_active = active_count

                    wait_time = time.monotonic() - wait_start
                    start_time = time.monotonic()
                    logger.debug(
                        f"[EMBED] Batch {batch_idx + 1}/{len(sub_batches)} STARTED "
                        f"(texts={len(sub_batch)}, active={current_active}, wait={wait_time:.2f}s)"
                    )

                    try:
                        result = await self._embed_sub_batch(sub_batch, logger, output_dims)
                        elapsed = time.monotonic() - start_time
                        logger.debug(
                            f"[EMBED] Batch {batch_idx + 1}/{len(sub_batches)} DONE "
                            f"in {elapsed:.2f}s (texts={len(sub_batch)})"
                        )
                        return result
                    finally:
                        async with active_lock:
                            active_count -= 1

            # Execute all sub-batches concurrently (limited by semaphore)
            results = await asyncio.gather(
                *[embed_with_semaphore(i, sb) for i, sb in enumerate(sub_batches)]
            )

            total_time = time.monotonic() - batch_start_time
            logger.debug(
                f"[EMBED] All {len(sub_batches)} sub-batches completed in {total_time:.2f}s "
                f"(avg {total_time / len(sub_batches):.2f}s/batch)"
            )

            # Flatten results while preserving order
            return [emb for batch_result in results for emb in batch_result]

        # Check if we need to split due to token limit
        if total_tokens > self.MAX_TOKENS_PER_REQUEST:
            logger.debug(f"Batch exceeds {self.MAX_TOKENS_PER_REQUEST} tokens, splitting in half")
            mid = len(texts) // 2
            first_half = await self.embed_many(texts[:mid], context, dimensions)
            second_half = await self.embed_many(texts[mid:], context, dimensions)
            return first_half + second_half

        # Process single request with rate limiting
        embeddings = await self._embed_batch(texts, logger, output_dims)

        # Validate result count matches input count
        if len(embeddings) != len(texts):
            raise SyncFailureError(
                f"PROGRAMMING ERROR: Got {len(embeddings)} embeddings for {len(texts)} texts"
            )

        return embeddings

    async def _embed_sub_batch(
        self, texts: List[str], logger: ContextualLogger, output_dims: int
    ) -> List[List[float]]:
        """Embed a sub-batch, handling token limit splitting if needed.

        This is called from concurrent processing and handles cases where
        a sub-batch exceeds the token limit by splitting recursively.

        Texts that individually exceed the token limit are skipped with a
        zero vector to avoid crashing the entire sync pipeline.

        Args:
            texts: List of texts to embed (already within count limit)
            logger: Logger for debug output
            output_dims: Output dimension for embeddings

        Returns:
            List of embedding vectors (zero vectors for skipped texts)
        """
        if not texts:
            return []

        # Count tokens for each text individually
        # Use allowed_special="all" to handle special tokens like <|endoftext|>
        token_counts = [len(self._tokenizer.encode(text, allowed_special="all")) for text in texts]
        total_tokens = sum(token_counts)

        # Handle single text that exceeds the limit - skip it gracefully
        if len(texts) == 1 and total_tokens > self.MAX_TOKENS_PER_REQUEST:
            logger.warning(
                f"[EMBED] Skipping text with {total_tokens} tokens "
                f"(exceeds {self.MAX_TOKENS_PER_REQUEST} limit). "
                f"Text preview: {texts[0][:200]}..."
            )
            # Return zero vector so the pipeline continues
            return [[0.0] * output_dims]

        # Check if we need to split due to token limit
        if total_tokens > self.MAX_TOKENS_PER_REQUEST:
            logger.debug(
                f"Sub-batch exceeds {self.MAX_TOKENS_PER_REQUEST} tokens, splitting in half"
            )
            mid = len(texts) // 2
            first_half = await self._embed_sub_batch(texts[:mid], logger, output_dims)
            second_half = await self._embed_sub_batch(texts[mid:], logger, output_dims)
            return first_half + second_half

        # Process single request
        return await self._embed_batch(texts, logger, output_dims)

    async def _embed_batch(
        self, batch: List[str], logger: ContextualLogger, output_dims: int
    ) -> List[List[float]]:
        """Embed single batch with rate limiting and error handling.

        Args:
            batch: List of texts to embed (must fit in one OpenAI request)
            logger: Logger for debug output
            output_dims: Output dimension for embeddings (Matryoshka support)

        Returns:
            List of embedding vectors

        Raises:
            SyncFailureError: On any API error
        """
        try:
            # Rate limit (singleton shared across pod)
            rate_limit_start = time.monotonic()
            await self._rate_limiter.acquire()
            rate_limit_wait = time.monotonic() - rate_limit_start

            # Call OpenAI API with explicit dimensions (Matryoshka support)
            api_start = time.monotonic()
            response = await self._client.embeddings.create(
                input=batch,
                model=self.MODEL_NAME,
                dimensions=output_dims,  # Matryoshka: request specific dimension
                encoding_format="float",
            )
            api_time = time.monotonic() - api_start

            # Log timing breakdown
            if rate_limit_wait > 0.1 or api_time > 5.0:
                logger.debug(
                    f"[EMBED] API call: {len(batch)} texts -> {output_dims}-dim, "
                    f"rate_limit_wait={rate_limit_wait:.2f}s, api_time={api_time:.2f}s"
                )

            # Extract embeddings
            embeddings = [e.embedding for e in response.data]

            # Validate response
            if len(embeddings) != len(batch):
                raise SyncFailureError(
                    f"OpenAI returned {len(embeddings)} embeddings for {len(batch)} texts"
                )

            # Validate dimensions match requested
            if embeddings and len(embeddings[0]) != output_dims:
                raise SyncFailureError(
                    f"OpenAI returned {len(embeddings[0])}-dim vectors, expected {output_dims}"
                )

            return embeddings

        except SyncFailureError:
            # Re-raise SyncFailureError as-is
            raise
        except Exception as e:
            error_msg = str(e).lower()

            # Token limit error - skip batch gracefully with zero vectors
            # This shouldn't happen if _embed_sub_batch worked, but handle it as fallback
            if "maximum context length" in error_msg or "max_tokens" in error_msg:
                logger.error(
                    f"[EMBED] Token limit exceeded for batch of {len(batch)} texts, "
                    f"returning zero vectors. Error: {e}"
                )
                return [[0.0] * output_dims for _ in batch]

            # Other transient errors - log and skip batch
            # Don't kill the entire sync for a single batch failure
            logger.error(
                f"[EMBED] OpenAI API error for batch of {len(batch)} texts, "
                f"returning zero vectors. Error: {e}"
            )
            return [[0.0] * output_dims for _ in batch]
