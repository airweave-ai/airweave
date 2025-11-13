"""Dense embedder supporting both OpenAI and local embedding models."""

import asyncio
from typing import List

import tiktoken
from openai import AsyncOpenAI

from airweave.core.config import settings
from airweave.platform.rate_limiters.openai import OpenAIRateLimiter
from airweave.platform.sync.context import SyncContext
from airweave.platform.sync.exceptions import SyncFailureError

from ._base import BaseEmbedder


class DenseEmbedder(BaseEmbedder):
    """Dense embedder with dynamic model selection (non-singleton).

    IMPORTANT: No longer a singleton! Each collection may use different embedding models,
    so we create fresh instances with the correct model for each sync/search operation.

    Supports both OpenAI and local embedding models:
    - 384-dim: Local MiniLM-L6-v2 via TEXT2VEC service (no API key needed)
    - 1536-dim: OpenAI text-embedding-3-small (requires OPENAI_API_KEY)
    - 3072-dim: OpenAI text-embedding-3-large (requires OPENAI_API_KEY)

    Features:
    - Dynamic model selection based on vector_size
    - Batch processing with appropriate limits per provider
    - Rate limiting for OpenAI (shared across instances)
    - Automatic retry on transient errors
    - Fail-fast on any API errors (no silent failures)
    """

    MAX_TOKENS_PER_TEXT = 8192  # OpenAI limit per text
    MAX_BATCH_SIZE = 2048  # OpenAI limit per request
    MAX_TOKENS_PER_REQUEST = 300000  # OpenAI limit
    MAX_CONCURRENT_REQUESTS = 5

    def __new__(cls, vector_size: int = None):
        """Override singleton pattern from BaseEmbedder - create fresh instances."""
        return object.__new__(cls)

    def __init__(self, vector_size: int = None):
        """Initialize OpenAI embedder for specific vector dimensions.

        Args:
            vector_size: Vector dimensions to determine model:
                - 3072: text-embedding-3-large
                - 1536: text-embedding-3-small
                - 384: local MiniLM-L6-v2 (via TEXT2VEC service)
                - None: defaults to 3072 (large model)
        """
        # Fail-fast: vector_size should always be provided from collection
        # Only allow None for backward compatibility, but warn
        if vector_size is None:
            # Fallback to large model but this shouldn't happen
            vector_size = 3072

        self.VECTOR_DIMENSIONS = vector_size

        # Check if this is a local embedding model (384-dim = MiniLM-L6-v2)
        if vector_size == 384:
            # Use local text2vec service - no OpenAI API key needed
            self.MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
            self._client = None  # No OpenAI client needed
            self._rate_limiter = None  # No rate limiter needed for local service
            self._tokenizer = tiktoken.get_encoding("cl100k_base")
        else:
            # OpenAI models (1536 or 3072) - require API key
            if not settings.OPENAI_API_KEY:
                raise SyncFailureError(
                    f"OPENAI_API_KEY required for {vector_size}-dim embeddings. "
                    f"Either configure OPENAI_API_KEY or use 384-dim collections with local embeddings."
                )

            # Select model and dimensions based on vector_size
            from airweave.platform.destinations.collection_strategy import (
                get_openai_embedding_model_for_vector_size,
            )

            self.MODEL_NAME = get_openai_embedding_model_for_vector_size(vector_size)

            # Create fresh client instance
            self._client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                timeout=1200.0,  # 20 min timeout for high concurrency
                max_retries=2,
            )
            self._rate_limiter = OpenAIRateLimiter()  # This singleton is still OK (shared rate limit)
            self._tokenizer = tiktoken.get_encoding("cl100k_base")

    async def embed_many(self, texts: List[str], sync_context: SyncContext) -> List[List[float]]:
        """Embed batch of texts using the appropriate embedding service.

        Routes to OpenAI (1536/3072-dim) or local text2vec (384-dim) based on vector_size.
        Returns exactly len(texts) vectors. Raises SyncFailureError on ANY error (no silent failures).

        Args:
            texts: List of text strings to embed (must not be empty)
            sync_context: Sync context with logger

        Returns:
            List of embedding vectors with dimensions matching self.VECTOR_DIMENSIONS

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

        # Split into smaller batches to avoid blocking and allow heartbeats
        # Max 200 texts per sub-batch to prevent long blocking periods
        MAX_TEXTS_PER_SUBBATCH = 200

        if len(texts) > MAX_TEXTS_PER_SUBBATCH:
            sync_context.logger.debug(
                f"Splitting {len(texts)} texts into sub-batches of {MAX_TEXTS_PER_SUBBATCH} "
                f"to allow heartbeats and prevent Temporal timeout"
            )
            all_embeddings = []
            for i in range(0, len(texts), MAX_TEXTS_PER_SUBBATCH):
                sub_batch = texts[i : i + MAX_TEXTS_PER_SUBBATCH]
                sub_embeddings = await self.embed_many(sub_batch, sync_context)
                all_embeddings.extend(sub_embeddings)
                # Yield control to event loop between sub-batches
                await asyncio.sleep(0)
            return all_embeddings

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

    async def _embed_batch(self, batch: List[str], sync_context: SyncContext) -> List[List[float]]:
        """Embed single batch with rate limiting and error handling.

        Args:
            batch: List of texts to embed (must fit in one request)
            sync_context: Sync context with logger

        Returns:
            List of embedding vectors

        Raises:
            SyncFailureError: On any API error
        """
        # Route to appropriate embedding service
        if self.VECTOR_DIMENSIONS == 384:
            return await self._embed_batch_local(batch, sync_context)
        else:
            return await self._embed_batch_openai(batch, sync_context)

    async def _embed_batch_local(self, batch: List[str], sync_context: SyncContext) -> List[List[float]]:
        """Embed batch using local text2vec service.

        Args:
            batch: List of texts to embed
            sync_context: Sync context with logger

        Returns:
            List of 384-dim embedding vectors

        Raises:
            SyncFailureError: On any API error
        """
        try:
            import httpx

            # Call local text2vec service
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{settings.TEXT2VEC_INFERENCE_URL}/.weaviate/v1.0/modules/text2vec-transformers/passages",
                    json={"text": batch},
                )
                response.raise_for_status()
                result = response.json()

            # Extract embeddings from response
            embeddings = result.get("vectors", [])

            # Validate response
            if len(embeddings) != len(batch):
                raise SyncFailureError(
                    f"Local service returned {len(embeddings)} embeddings for {len(batch)} texts"
                )

            # Validate dimensions
            if embeddings and len(embeddings[0]) != self.VECTOR_DIMENSIONS:
                raise SyncFailureError(
                    f"Local service returned {len(embeddings[0])}-dim vectors, "
                    f"expected {self.VECTOR_DIMENSIONS}"
                )

            return embeddings

        except SyncFailureError:
            # Re-raise SyncFailureError as-is
            raise
        except Exception as e:
            sync_context.logger.error(f"Local embedding service error: {e}")
            raise SyncFailureError(f"Local embedding failed: {e}")

    async def _embed_batch_openai(self, batch: List[str], sync_context: SyncContext) -> List[List[float]]:
        """Embed batch using OpenAI API.

        Args:
            batch: List of texts to embed
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
