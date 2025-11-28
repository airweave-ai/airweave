"""OpenAI dense embedder using text-embedding-3-large."""

import asyncio
import time
from typing import List

import tiktoken
from openai import AsyncOpenAI

from airweave.core.config import settings
from airweave.platform.rate_limiters.openai import OpenAIRateLimiter
from airweave.platform.sync.context import SyncContext
from airweave.platform.sync.exceptions import SyncFailureError

from ._base import BaseEmbedder


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
        # Use allowed_special="all" to handle special tokens like <|endoftext|>
        # that may appear in user content
        total_tokens = sum(
            len(self._tokenizer.encode(text, allowed_special="all")) for text in texts
        )

        sync_context.logger.debug(f"Embedding {len(texts)} texts with {total_tokens} total tokens")

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

            sync_context.logger.debug(
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
                    sync_context.logger.debug(
                        f"[EMBED] Batch {batch_idx + 1}/{len(sub_batches)} STARTED "
                        f"(texts={len(sub_batch)}, active={current_active}, wait={wait_time:.2f}s)"
                    )

                    try:
                        result = await self._embed_sub_batch(sub_batch, sync_context)
                        elapsed = time.monotonic() - start_time
                        sync_context.logger.debug(
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
            sync_context.logger.debug(
                f"[EMBED] All {len(sub_batches)} sub-batches completed in {total_time:.2f}s "
                f"(avg {total_time / len(sub_batches):.2f}s/batch)"
            )

            # Flatten results while preserving order
            return [emb for batch_result in results for emb in batch_result]

        # Check if we need to split due to token limit
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

    async def _embed_sub_batch(
        self, texts: List[str], sync_context: SyncContext
    ) -> List[List[float]]:
        """Embed a sub-batch, handling token limit splitting if needed.

        This is called from concurrent processing and handles cases where
        a sub-batch exceeds the token limit by splitting recursively.

        Args:
            texts: List of texts to embed (already within count limit)
            sync_context: Sync context with logger

        Returns:
            List of embedding vectors
        """
        # Count tokens for this sub-batch
        total_tokens = sum(len(self._tokenizer.encode(text)) for text in texts)

        # Check if we need to split due to token limit
        if total_tokens > self.MAX_TOKENS_PER_REQUEST:
            sync_context.logger.debug(
                f"Sub-batch exceeds {self.MAX_TOKENS_PER_REQUEST} tokens, splitting in half"
            )
            mid = len(texts) // 2
            first_half = await self._embed_sub_batch(texts[:mid], sync_context)
            second_half = await self._embed_sub_batch(texts[mid:], sync_context)
            return first_half + second_half

        # Process single request
        return await self._embed_batch(texts, sync_context)

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
            rate_limit_start = time.monotonic()
            await self._rate_limiter.acquire()
            rate_limit_wait = time.monotonic() - rate_limit_start

            # Call OpenAI API
            api_start = time.monotonic()
            response = await self._client.embeddings.create(
                input=batch,
                model=self.MODEL_NAME,
                encoding_format="float",
            )
            api_time = time.monotonic() - api_start

            # Log timing breakdown
            if rate_limit_wait > 0.1 or api_time > 5.0:
                sync_context.logger.debug(
                    f"[EMBED] API call: {len(batch)} texts, "
                    f"rate_limit_wait={rate_limit_wait:.2f}s, api_time={api_time:.2f}s"
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
