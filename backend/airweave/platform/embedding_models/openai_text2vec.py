"""OpenAI text2vec model for embedding."""

import time
from typing import List, Optional

import httpx
from pydantic import Field

from airweave.core.logging import logger
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
            logger.debug("Empty text provided for embedding, returning zero vector")
            # Return zero vector for empty text
            return [0.0] * self.vector_dimensions

        used_model = model or self.embedding_model
        logger.debug(f"Embedding single text with model {used_model} (text length: {len(text)})")

        start_time = time.time()
        try:
            async with httpx.AsyncClient() as client:
                logger.debug("Sending embedding request to OpenAI API")
                response = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"input": text, "model": used_model, "encoding_format": encoding_format},
                    timeout=60.0,  # Add longer timeout
                )
                response.raise_for_status()
                result = response.json()["data"][0]["embedding"]
                elapsed = time.time() - start_time
                logger.debug(f"Embedding completed in {elapsed:.2f}s, vector size: {len(result)}")
                return result
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenAI API HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"OpenAI API request error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during embedding: {str(e)}")
            raise

    async def _process_empty_texts(self, texts: List[str]) -> tuple:
        """Process texts to separate empty from non-empty.

        Returns:
            Tuple of (filtered_texts, empty_indices)
        """
        filtered_texts = []
        empty_indices = []

        for i, text in enumerate(texts):
            if text.strip():
                filtered_texts.append(text)
            else:
                empty_indices.append(i)

        return filtered_texts, empty_indices

    async def _make_openai_request(
        self, filtered_texts: List[str], used_model: str, encoding_format: str
    ) -> List:
        """Make the actual request to OpenAI API.

        Returns:
            List of embeddings
        """
        max_text_length = max(len(text) for text in filtered_texts) if filtered_texts else 0
        logger.debug(f"Maximum text length in batch: {max_text_length} chars")

        async with httpx.AsyncClient() as client:
            logger.debug(f"Sending batch embedding request to OpenAI API using model {used_model}")
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
                timeout=120.0,  # Longer timeout for batches
            )
            response.raise_for_status()
            return [e["embedding"] for e in response.json()["data"]]

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
            logger.debug("Empty texts list provided for embedding")
            return []

        # Log batch size
        logger.info(f"Embedding batch of {len(texts)} texts")

        # Filter out empty texts and track their positions
        filtered_texts, empty_indices = await self._process_empty_texts(texts)

        if not filtered_texts:
            logger.debug("All texts in batch were empty, returning zero vectors")
            return [[0.0] * self.vector_dimensions] * len(texts)

        # Log actual texts to embed
        logger.debug(
            f"Embedding {len(filtered_texts)} non-empty texts "
            f"(skipped {len(empty_indices)} empty texts)"
        )

        used_model = model or self.embedding_model
        start_time = time.time()

        try:
            embeddings = await self._make_openai_request(
                filtered_texts, used_model, encoding_format
            )
            elapsed = time.time() - start_time
            logger.info(f"Batch embedding completed in {elapsed:.2f}s ({len(embeddings)} vectors)")

            # Reinsert empty vectors at the correct positions
            result = []
            embedding_idx = 0

            for i in range(len(texts)):
                if i in empty_indices:
                    result.append([0.0] * self.vector_dimensions)
                else:
                    result.append(embeddings[embedding_idx])
                    embedding_idx += 1

            logger.debug(f"Final result contains {len(result)} vectors")
            return result
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenAI API HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"OpenAI API request error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during batch embedding: {str(e)}")
            raise
