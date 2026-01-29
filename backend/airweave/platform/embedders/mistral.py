"""Mistral dense embedder for client-side embeddings."""

import asyncio
import hashlib
import random
import time
from typing import TYPE_CHECKING, List, Optional, Union

try:
    from mistralai import Mistral
except ImportError:
    Mistral = None  # type: ignore[assignment]

from airweave.core.config import settings
from airweave.core.logging import ContextualLogger
from airweave.core.logging import logger as default_logger
from airweave.platform.embedders.config import is_mock_model
from airweave.platform.rate_limiters.mistral import MistralRateLimiter
from airweave.platform.sync.async_helpers import run_in_thread_pool
from airweave.platform.sync.exceptions import SyncFailureError
from airweave.platform.tokenizers import get_tokenizer

from ._base import BaseEmbedder

if TYPE_CHECKING:
    from airweave.platform.contexts import SyncContext


class MistralDenseEmbedder(BaseEmbedder):
    """Mistral dense embedder with fixed-dimension models."""

    MAX_BATCH_SIZE = 128
    MAX_CONCURRENT_REQUESTS = 5
    MAX_TOKENS_PER_REQUEST = 8000

    def __new__(cls, *args, **kwargs):
        """Override singleton pattern from BaseEmbedder - create fresh instances."""
        return object.__new__(cls)

    def __init__(self, model_name: str, vector_size: Optional[int] = None) -> None:
        """Initialize Mistral embedder.

        Args:
            model_name: Mistral model name (e.g., "mistral-embed")
            vector_size: Output dimensions (default: settings.EMBEDDING_DIMENSIONS)
        """
        self._mock_embeddings = is_mock_model(model_name)
        if not self._mock_embeddings:
            if not settings.MISTRAL_API_KEY:
                raise SyncFailureError("MISTRAL_API_KEY required for Mistral embeddings")
            if Mistral is None:
                raise SyncFailureError("mistralai package required but not installed")

        self.MODEL_NAME = model_name
        self.VECTOR_DIMENSIONS = vector_size or settings.EMBEDDING_DIMENSIONS
        self._tokenizer = get_tokenizer(model_name)
        self._client = None
        self._rate_limiter = None
        if not self._mock_embeddings:
            self._client = Mistral(api_key=settings.MISTRAL_API_KEY)
            self._rate_limiter = MistralRateLimiter()

    def _get_logger(
        self, context: Union["SyncContext", ContextualLogger, None]
    ) -> ContextualLogger:
        """Extract logger from context."""
        if context is None:
            return default_logger
        if isinstance(context, ContextualLogger):
            return context
        return context.logger

    def _validate_texts(self, texts: List[str]) -> None:
        """Validate texts are non-empty."""
        for i, text in enumerate(texts):
            if not text or not text.strip():
                raise SyncFailureError(
                    f"PROGRAMMING ERROR: Empty text at index {i}. "
                    f"Textual representation must be set before embedding."
                )

    def _call_embeddings_api(self, batch: List[str]) -> List[List[float]]:
        """Call Mistral embeddings API synchronously."""
        request = {"model": self.MODEL_NAME, "inputs": batch}
        if self._client is None:
            raise SyncFailureError("Mistral client is not initialized")
        try:
            response = self._client.embeddings.create(**request)
        except TypeError as exc:
            if "unexpected keyword argument 'inputs'" in str(exc):
                request["input"] = request.pop("inputs")
                response = self._client.embeddings.create(**request)
            else:
                raise

        if not response.data:
            raise SyncFailureError("Mistral returned no embeddings")

        embeddings = [item.embedding for item in response.data]
        if len(embeddings) != len(batch):
            raise SyncFailureError(
                f"Mistral returned {len(embeddings)} embeddings for {len(batch)} texts"
            )
        return embeddings

    async def _embed_single_batch(
        self, batch_idx: int, batch: List[str], total_batches: int, semaphore: asyncio.Semaphore
    ) -> List[List[float]]:
        """Embed a single batch with rate limiting."""
        async with semaphore:
            if self._rate_limiter is None:
                raise SyncFailureError("Mistral rate limiter is not initialized")
            await self._rate_limiter.acquire()
            start_time = time.monotonic()

            embeddings = await run_in_thread_pool(lambda: self._call_embeddings_api(batch))

            elapsed = time.monotonic() - start_time
            if elapsed > 5.0:
                default_logger.debug(
                    f"[EMBED] Mistral batch {batch_idx + 1}/{total_batches} "
                    f"({len(batch)} texts) took {elapsed:.2f}s"
                )
            return embeddings

    async def _embed_batches(self, texts: List[str]) -> List[List[float]]:
        """Embed texts in parallel batches."""
        batches = [
            texts[i : i + self.MAX_BATCH_SIZE] for i in range(0, len(texts), self.MAX_BATCH_SIZE)
        ]
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)
        results = await asyncio.gather(
            *[
                self._embed_single_batch(i, batch, len(batches), semaphore)
                for i, batch in enumerate(batches)
            ]
        )
        return [emb for batch in results for emb in batch]

    async def _embed_with_token_limits(
        self, texts: List[str], dimensions: int, logger: ContextualLogger
    ) -> List[List[float]]:
        """Embed texts, splitting if token limits exceeded."""
        if not texts:
            return []

        total_tokens = sum(self._tokenizer.count_tokens(text) for text in texts)

        if len(texts) == 1 and total_tokens > self.MAX_TOKENS_PER_REQUEST:
            logger.warning(
                f"[EMBED] Skipping text with {total_tokens} tokens "
                f"(max {self.MAX_TOKENS_PER_REQUEST})"
            )
            return [[0.0] * dimensions]

        if total_tokens > self.MAX_TOKENS_PER_REQUEST:
            logger.debug(f"[EMBED] Batch exceeds {self.MAX_TOKENS_PER_REQUEST} tokens, splitting")
            mid = len(texts) // 2
            first_half = await self._embed_with_token_limits(texts[:mid], dimensions, logger)
            second_half = await self._embed_with_token_limits(texts[mid:], dimensions, logger)
            return first_half + second_half

        return await self._embed_batches(texts)

    async def embed_many(
        self,
        texts: List[str],
        context: Union["SyncContext", ContextualLogger, None] = None,
        dimensions: Optional[int] = None,
    ) -> List[List[float]]:
        """Embed batch of texts using Mistral embeddings."""
        logger = self._get_logger(context)

        if not texts:
            return []

        self._validate_texts(texts)

        # mistral-embed always outputs 1024 dimensions (no custom dimension support)
        MISTRAL_FIXED_DIMENSIONS = 1024
        requested_dimensions = dimensions or self.VECTOR_DIMENSIONS

        if self._mock_embeddings:
            return self._mock_embed_many(texts, requested_dimensions)

        if requested_dimensions != MISTRAL_FIXED_DIMENSIONS:
            raise SyncFailureError(
                f"Mistral embeddings are fixed at {MISTRAL_FIXED_DIMENSIONS} dimensions. "
                f"Requested {requested_dimensions}. Use OpenAI for custom dimensions."
            )

        return await self._embed_with_token_limits(texts, requested_dimensions, logger)

    @staticmethod
    def _mock_embed_many(texts: List[str], dimensions: Optional[int]) -> List[List[float]]:
        """Return deterministic mock embeddings without external API calls."""
        if not dimensions:
            raise SyncFailureError("Mock Mistral embeddings require explicit dimensions")

        embeddings: List[List[float]] = []
        for text in texts:
            seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
            rng = random.Random(seed)
            embeddings.append([rng.uniform(-1.0, 1.0) for _ in range(dimensions)])

        return embeddings
