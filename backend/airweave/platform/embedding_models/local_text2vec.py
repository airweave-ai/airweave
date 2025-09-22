"""Local text2vec model for embedding."""

from typing import List, Optional

import httpx
from pydantic import Field

from airweave.core.config import settings
from airweave.core.logging import ContextualLogger
from airweave.platform.decorators import embedding_model
from airweave.platform.transformers.utils import count_tokens

from ._base import BaseEmbeddingModel


@embedding_model(
    "Local Text2Vec",
    "local_text2vec",
    "local",
    model_name="local-text2vec-transformers",
    model_version="1.0",
)
class LocalText2Vec(BaseEmbeddingModel):
    """Local text2vec model configuration for embedding."""

    # Configuration parameters as class attributes
    vector_dimensions: int = 384  # MiniLM-L6-v2 default dimensions
    model_name: str = "local-text2vec-transformers"
    enabled: bool = True
    inference_url: str = Field(
        default="", description="URL of the inference API"
    )  # Updated during initialization

    def __init__(
        self,
        logger: Optional[ContextualLogger] = None,
        **data,  # Pass through to BaseEmbeddingModel/Pydantic, if relevant
    ):
        """Initialize the local text2vec model."""
        # Always call parent __init__ (esp. with Pydantic models!)
        super().__init__(**data)
        self.inference_url = settings.TEXT2VEC_INFERENCE_URL
        if logger:
            self.logger = logger  # Override with contextual logger if provided
            self.logger.debug(f"Text2Vec model using inference URL: {self.inference_url}")

    def _should_skip_text(self, text: str) -> bool:
        """Check if text should be skipped due to token limit."""
        if not text.strip():
            return False
        
        token_count = count_tokens(text)
        if token_count > 250:
            if hasattr(self, "logger") and self.logger:
                self.logger.warning(f"Skipping text with {token_count} tokens (>250 limit)")
            return True
        return False

    async def embed(
        self,
        text: str,
        model: Optional[str] = None,
        encoding_format: str = "float",
        dimensions: Optional[int] = None,
    ) -> List[float]:
        """Embed a single text string using the local text2vec model.

        Args:
            text: The text to embed
            model: Optional model override (defaults to self.model_name)
            encoding_format: Format of the embedding (default: float)
            dimensions: Vector dimensions (defaults to self.vector_dimensions)

        Returns:
            List of embedding values
        """
        if model:
            raise ValueError("Model override not supported for local text2vec")

        if dimensions:
            raise ValueError("Dimensions override not supported for local text2vec")

        if not text.strip():
            # Return zero vector for empty text
            return [0.0] * self.vector_dimensions

        # Skip texts with >200 tokens to avoid ReadTimeout
        if self._should_skip_text(text):
            return [0.0] * self.vector_dimensions

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.inference_url}/vectors", json={"text": text})
            response.raise_for_status()
            return response.json()["vector"]

    async def embed_many(
        self,
        texts: List[str],
        model: Optional[str] = None,
        encoding_format: str = "float",
        dimensions: Optional[int] = None,
    ) -> List[List[float]]:
        """Embed multiple text strings using the local text2vec model.

        Args:
            texts: List of texts to embed
            model: Optional model override (defaults to self.model_name)
            encoding_format: Format of the embedding (default: float)
            dimensions: Vector dimensions (defaults to self.vector_dimensions)

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        if model:
            raise ValueError("Model override not supported for local text2vec")

        if dimensions:
            raise ValueError("Dimensions override not supported for local text2vec")

        # Create result list with same order as input
        result = []

        # Process each text individually since batch endpoint isn't available
        async with httpx.AsyncClient() as client:
            for text in texts:
                if not text.strip() or self._should_skip_text(text):
                    result.append([0.0] * self.vector_dimensions)
                else:
                    try:
                        response = await client.post(
                            f"{self.inference_url}/vectors/", json={"text": text}
                        )
                        response.raise_for_status()
                        result.append(response.json()["vector"])
                    except Exception as e:
                        if hasattr(self, "logger") and self.logger:
                            self.logger.error(f"Error embedding text: {e}")
                        # Return zero vector for failed embedding
                        result.append([0.0] * self.vector_dimensions)

        return result
