"""OpenAI dense embedder for agentic search.

Uses text-embedding-3-small/large models with Matryoshka dimension support.
Simple, fail-fast implementation for query embedding (1-5 queries per search).
"""

from openai import AsyncOpenAI

from airweave.core.config import settings
from airweave.search.agentic_search.external.dense_embedder.registry import (
    DenseEmbedderModelSpec,
)
from airweave.search.agentic_search.schemas.plan import AgenticSearchQuery
from airweave.search.agentic_search.schemas.query_embeddings import AgenticSearchDenseEmbedding


class OpenAIDenseEmbedder:
    """OpenAI dense embedder for agentic search.

    Features:
    - Model spec and vector_size provided at init (selected by services)
    - Matryoshka dimension support via `dimensions` parameter
    - Built-in retry via AsyncOpenAI (max_retries=2)
    - Fail-fast on any errors
    """

    # OpenAI limits
    MAX_TOKENS_PER_TEXT = 8192
    MAX_BATCH_SIZE = 2048
    MAX_TOKENS_PER_REQUEST = 300_000

    def __init__(self, model_spec: DenseEmbedderModelSpec, vector_size: int) -> None:
        """Initialize the OpenAI embedder.

        Args:
            model_spec: Model specification from the registry.
            vector_size: Embedding dimension to request from the API.

        Raises:
            ValueError: If OPENAI_API_KEY is not configured.
            ValueError: If vector_size requires dimension param but model doesn't support it.
        """
        if not settings.OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY not configured. Set it in your environment or .env file."
            )

        # Validate dimension compatibility
        if not model_spec.supports_dimension_param:
            if vector_size != model_spec.default_dimensions:
                raise ValueError(
                    f"Model '{model_spec.api_model_name}' does not support custom dimensions. "
                    f"Collection requires {vector_size} dimensions but model only produces "
                    f"{model_spec.default_dimensions}."
                )

        self._model_spec = model_spec
        self._vector_size = vector_size

        self._client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=60.0,
            max_retries=2,
        )

    @property
    def model_spec(self) -> DenseEmbedderModelSpec:
        """Get the model specification."""
        return self._model_spec

    async def embed_batch(self, query: AgenticSearchQuery) -> list[AgenticSearchDenseEmbedding]:
        """Embed primary query and all variations.

        Args:
            query: Search query containing primary and optional variations.

        Returns:
            List of dense embeddings, one per query text.
            Order: [primary_embedding, variation_1_embedding, ...].

        Raises:
            ValueError: If query texts are empty.
            RuntimeError: If OpenAI API call fails.
        """
        # Build list of texts to embed
        texts = [query.primary] + list(query.variations)

        # Validate
        for i, text in enumerate(texts):
            if not text or not text.strip():
                raise ValueError(f"Empty query text at index {i}")

        # Build API call parameters
        api_params: dict = {
            "input": texts,
            "model": self._model_spec.api_model_name,
            "encoding_format": "float",
        }

        # Only include dimensions if model supports it
        if self._model_spec.supports_dimension_param:
            api_params["dimensions"] = self._vector_size

        # Call OpenAI API
        try:
            response = await self._client.embeddings.create(**api_params)
        except Exception as e:
            raise RuntimeError(f"OpenAI embedding API call failed: {e}") from e

        # Extract embeddings
        embeddings = [item.embedding for item in response.data]

        # Validate response
        if len(embeddings) != len(texts):
            raise RuntimeError(
                f"OpenAI returned {len(embeddings)} embeddings for {len(texts)} texts"
            )

        if embeddings and len(embeddings[0]) != self._vector_size:
            raise RuntimeError(
                f"OpenAI returned {len(embeddings[0])}-dim vectors, expected {self._vector_size}"
            )

        # Convert to schema
        return [AgenticSearchDenseEmbedding(vector=emb) for emb in embeddings]

    async def close(self) -> None:
        """Clean up resources.

        AsyncOpenAI client doesn't require explicit cleanup,
        but we implement this for interface compliance.
        """
        pass
