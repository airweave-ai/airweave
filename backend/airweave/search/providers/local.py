"""Local provider for 384-dim embeddings using TEXT2VEC service."""

from typing import Any, Dict, List

from pydantic import BaseModel

from airweave.api.context import ApiContext
from airweave.platform.embedders import DenseEmbedder

from ._base import BaseProvider
from .schemas import ProviderModelSpec


class LocalProvider(BaseProvider):
    """Local provider for 384-dim embeddings via TEXT2VEC service.

    This provider wraps the DenseEmbedder for use in the search system,
    enabling 384-dim collections to work without requiring an OpenAI API key.
    """

    def __init__(
        self, api_key: str, model_spec: ProviderModelSpec, ctx: ApiContext, vector_size: int = 384
    ) -> None:
        """Initialize local provider.

        Args:
            api_key: Unused for local provider (kept for interface compatibility)
            model_spec: Model specifications (unused for local embeddings)
            ctx: API context
            vector_size: Vector dimensions (should be 384 for local embeddings)
        """
        super().__init__(api_key, model_spec, ctx)
        self.vector_size = vector_size

        # Initialize DenseEmbedder for local embeddings
        self._embedder = DenseEmbedder(vector_size=vector_size)

    async def generate(self, messages: List[Dict[str, str]]) -> str:
        """Generate text completion - not supported by local provider."""
        raise NotImplementedError("Local provider does not support text generation")

    async def structured_output(
        self, messages: List[Dict[str, str]], schema: type[BaseModel]
    ) -> BaseModel:
        """Generate structured output - not supported by local provider."""
        raise NotImplementedError("Local provider does not support structured output")

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using local TEXT2VEC service.

        Args:
            texts: List of texts to embed

        Returns:
            List of 384-dim embedding vectors

        Raises:
            Exception: If embedding fails
        """
        if not texts:
            return []

        # Create minimal sync context for DenseEmbedder
        # DenseEmbedder expects sync_context but we only use it for logging
        from types import SimpleNamespace

        sync_context = SimpleNamespace(logger=self.ctx.logger)

        # Use DenseEmbedder to generate embeddings
        embeddings = await self._embedder.embed_many(texts, sync_context)

        return embeddings

    async def rerank(self, query: str, documents: List[str], top_n: int) -> List[Dict[str, Any]]:
        """Rerank documents - not supported by local provider."""
        raise NotImplementedError("Local provider does not support reranking")
