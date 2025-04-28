"""OpenAI text2vec model for embedding."""

from typing import List, Optional

import httpx
from pydantic import Field

from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import embedding_model

from ._base import BaseEmbeddingModel


@embedding_model(
    "OpenAI Text2Vec",
    "openai_text2vec",
    "openai",
    AuthType.config_class,
    "OpenAIAuthConfig",
)
class OpenAIText2Vec(BaseEmbeddingModel):
    """OpenAI text2vec model configuration for embedding."""

    model_name: str = "openai-text2vec"
    api_key: str = Field(..., description="OpenAI API key")
    vector_dimensions: int = 1536
    enabled: bool = True
    embedding_model: str = Field(
        default="text-embedding-3-small", description="OpenAI embedding model name"
    )

    async def embed(
        self,
        text: str,
        model: Optional[str] = None,
        encoding_format: str = "float",
        dimensions: Optional[int] = None,
    ) -> List[float]:
        """Embed a single text string using OpenAI.

        Args:
            text: The text to embed
            model: The OpenAI model to use (defaults to self.embedding_model)
            encoding_format: Format of the embedding (default: float)
            dimensions: Vector dimensions (defaults to self.vector_dimensions)

        Returns:
            List of embedding values
        """
        if dimensions:
            # OpenAI doesn't support custom dimensions - would need post-processing
            raise ValueError("Dimensions override not supported for OpenAI embedding")

        if not text.strip():
            # Return zero vector for empty text
            return [0.0] * self.vector_dimensions

        used_model = model or self.embedding_model

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={"input": text, "model": used_model, "encoding_format": encoding_format},
            )
            response.raise_for_status()
            return response.json()["data"][0]["embedding"]

    async def embed_many(
        self,
        texts: List[str],
        model: Optional[str] = None,
        encoding_format: str = "float",
        dimensions: Optional[int] = None,
    ) -> List[List[float]]:
        """Embed multiple text strings using OpenAI.

        Args:
            texts: List of texts to embed
            model: The OpenAI model to use (defaults to self.embedding_model)
            encoding_format: Format of the embedding (default: float)
            dimensions: Vector dimensions (defaults to self.vector_dimensions)

        Returns:
            List of embedding vectors
        """
        if dimensions:
            # OpenAI doesn't support custom dimensions - would need post-processing
            raise ValueError("Dimensions override not supported for OpenAI embedding")

        if not texts:
            return []

        # Filter out empty texts and track their positions
        filtered_texts = []
        empty_indices = []

        for i, text in enumerate(texts):
            if text.strip():
                filtered_texts.append(text)
            else:
                empty_indices.append(i)

        if not filtered_texts:
            return [[0.0] * self.vector_dimensions] * len(texts)

        used_model = model or self.embedding_model

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "input": filtered_texts,
                    "model": used_model,
                    "encoding_format": encoding_format,
                },
            )
            response.raise_for_status()

            # Get the embeddings in the same order as input
            embeddings = [e["embedding"] for e in response.json()["data"]]

            # Reinsert empty vectors at the correct positions
            result = []
            embedding_idx = 0

            for i in range(len(texts)):
                if i in empty_indices:
                    result.append([0.0] * self.vector_dimensions)
                else:
                    result.append(embeddings[embedding_idx])
                    embedding_idx += 1

            return result
