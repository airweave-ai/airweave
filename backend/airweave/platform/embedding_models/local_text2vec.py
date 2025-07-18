"""Local text2vec model for embedding."""

from typing import List, Optional

import httpx

from pydantic import Field
from airweave.core.config import settings
from airweave.core.logging import ContextualLogger
from airweave.platform.decorators import embedding_model

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
    inference_url: str = Field(default="", description="URL of the inference API") # Updated during initialization

    def __init__(
        self,
        logger: Optional[ContextualLogger] = None):
        self.logger = logger

    def model_post_init(self, __context) -> None:
        """Post initialization hook to set the inference URL from settings.

        This runs after Pydantic validation but before the model is used.
        """
        super().model_post_init(__context)
        self.inference_url = settings.TEXT2VEC_INFERENCE_URL
        self.logger.info(f"Text2Vec model using inference URL: {self.inference_url}")

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
                if text.strip():
                    try:
                        response = await client.post(
                            f"{self.inference_url}/vectors/", json={"text": text}
                        )
                        response.raise_for_status()
                        result.append(response.json()["vector"])
                    except Exception as e:
                        self.logger.error(f"Error embedding text: {e}")
                        # Return zero vector for failed embedding
                        result.append([0.0] * self.vector_dimensions)
                else:
                    # Return zero vector for empty text
                    result.append([0.0] * self.vector_dimensions)

        return result
