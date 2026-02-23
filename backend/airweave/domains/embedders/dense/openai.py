"""OpenAI dense embedder using text-embedding-3 models.

Supports Matryoshka embeddings via explicit dimension parameter for flexible
vector sizes (e.g., 768 for ranking, 96 for ANN search).
"""

import asyncio
from typing import List

import tiktoken
from openai import AsyncOpenAI

from airweave.core.logging import logger
from airweave.domains.embedders.dense.registry import DenseModelSpec
from airweave.domains.embedders.exceptions import EmbedderProviderError
from airweave.domains.embedders.schemas import DenseEmbedding
from airweave.platform.rate_limiters.openai import OpenAIRateLimiter


class OpenAIDenseEmbedder:
    """OpenAI dense embedder with configurable model and dimensions.

    Features:
    - Batch processing with OpenAI limits (2048 texts/request, 300K tokens/request)
    - 10 concurrent requests max
    - Rate limiting via OpenAIRateLimiter singleton
    - Automatic retry on transient errors (via AsyncOpenAI client)
    """

    MAX_TOKENS_PER_TEXT = 8192
    MAX_BATCH_SIZE = 2048
    MAX_TOKENS_PER_REQUEST = 300_000
    MAX_CONCURRENT_REQUESTS = 10

    def __init__(
        self,
        model_spec: DenseModelSpec,
        target_dimensions: int,
        api_key: str | None = None,
    ) -> None:
        """Initialize OpenAI embedder.

        Args:
            model_spec: Model specification from registry.
            target_dimensions: Output vector dimensions.
            api_key: OpenAI API key.  Falls back to settings if not provided.
        """
        if api_key is None:
            from airweave.core.config import settings

            api_key = settings.OPENAI_API_KEY

        if not api_key:
            raise EmbedderProviderError("OPENAI_API_KEY required for dense embeddings")

        self._model_spec = model_spec
        self._target_dimensions = target_dimensions
        self._client = AsyncOpenAI(
            api_key=api_key,
            timeout=1200.0,
            max_retries=2,
        )
        self._rate_limiter = OpenAIRateLimiter()
        self._tokenizer = tiktoken.get_encoding("cl100k_base")

    @property
    def vector_size(self) -> int:
        """Return the output dimension of this embedder."""
        return self._target_dimensions

    async def embed(self, text: str) -> DenseEmbedding:
        """Embed a single text."""
        results = await self.embed_many([text])
        return results[0]

    async def embed_many(self, texts: list[str]) -> list[DenseEmbedding]:
        """Embed batch of texts using OpenAI text-embedding-3 models."""
        if not texts:
            return []

        for i, text in enumerate(texts):
            if not text or not text.strip():
                raise EmbedderProviderError(
                    f"Empty text at index {i}. Textual representation must be set before embedding."
                )

        total_tokens = sum(
            len(self._tokenizer.encode(text, allowed_special="all")) for text in texts
        )

        logger.debug(
            f"Embedding {len(texts)} texts with {total_tokens} tokens "
            f"-> {self._target_dimensions}-dim vectors"
        )

        # Split into sub-batches for large inputs
        MAX_TEXTS_PER_SUBBATCH = 100

        if len(texts) > MAX_TEXTS_PER_SUBBATCH:
            sub_batches = [
                texts[i : i + MAX_TEXTS_PER_SUBBATCH]
                for i in range(0, len(texts), MAX_TEXTS_PER_SUBBATCH)
            ]

            semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)

            async def embed_with_semaphore(sub_batch: List[str]) -> list[DenseEmbedding]:
                async with semaphore:
                    return await self._embed_sub_batch(sub_batch)

            results = await asyncio.gather(*[embed_with_semaphore(sb) for sb in sub_batches])
            return [emb for batch_result in results for emb in batch_result]

        # Check token limit
        if total_tokens > self.MAX_TOKENS_PER_REQUEST:
            mid = len(texts) // 2
            first_half = await self.embed_many(texts[:mid])
            second_half = await self.embed_many(texts[mid:])
            return first_half + second_half

        return await self._embed_batch(texts)

    async def _embed_sub_batch(self, texts: list[str]) -> list[DenseEmbedding]:
        """Embed a sub-batch, handling token limit splitting if needed."""
        if not texts:
            return []

        token_counts = [len(self._tokenizer.encode(text, allowed_special="all")) for text in texts]
        total_tokens = sum(token_counts)

        if len(texts) == 1 and total_tokens > self.MAX_TOKENS_PER_REQUEST:
            logger.warning(
                f"Skipping text with {total_tokens} tokens "
                f"(exceeds {self.MAX_TOKENS_PER_REQUEST} limit)"
            )
            return [DenseEmbedding(vector=[0.0] * self._target_dimensions)]

        if total_tokens > self.MAX_TOKENS_PER_REQUEST:
            mid = len(texts) // 2
            first_half = await self._embed_sub_batch(texts[:mid])
            second_half = await self._embed_sub_batch(texts[mid:])
            return first_half + second_half

        return await self._embed_batch(texts)

    async def _embed_batch(self, batch: list[str]) -> list[DenseEmbedding]:
        """Embed single batch with rate limiting."""
        try:
            await self._rate_limiter.acquire()

            response = await self._client.embeddings.create(
                input=batch,
                model=self._model_spec.api_model_name,
                dimensions=self._target_dimensions,
                encoding_format="float",
            )

            embeddings = [DenseEmbedding(vector=e.embedding) for e in response.data]

            if len(embeddings) != len(batch):
                raise EmbedderProviderError(
                    f"OpenAI returned {len(embeddings)} embeddings for {len(batch)} texts"
                )

            if embeddings and len(embeddings[0].vector) != self._target_dimensions:
                raise EmbedderProviderError(
                    f"OpenAI returned {len(embeddings[0].vector)}-dim vectors, "
                    f"expected {self._target_dimensions}"
                )

            return embeddings

        except EmbedderProviderError:
            raise
        except Exception as e:
            error_msg = str(e).lower()
            if "maximum context length" in error_msg or "max_tokens" in error_msg:
                logger.error(f"Token limit exceeded for batch of {len(batch)} texts: {e}")
                return [DenseEmbedding(vector=[0.0] * self._target_dimensions) for _ in batch]

            logger.error(f"OpenAI API error for batch of {len(batch)} texts: {e}")
            return [DenseEmbedding(vector=[0.0] * self._target_dimensions) for _ in batch]

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.close()
