"""Base class for embedding models."""

from abc import abstractmethod
from typing import List, Optional

from pydantic import BaseModel


class BaseEmbeddingModel(BaseModel):
    """Abstract base class for embedding models.

    This base class defines a generic interface for embedding models
    that can be used with different vector stores.
    """

    model_name: str
    vector_dimensions: int
    enabled: bool = True

    @classmethod
    def create(cls, **kwargs) -> "BaseEmbeddingModel":
        """Create an instance of the embedding model."""
        return cls(**kwargs)

    @abstractmethod
    async def embed(
        self,
        text: str,
        model: Optional[str] = None,
        encoding_format: str = "float",
        dimensions: Optional[int] = None,
    ) -> List[float]:
        """Embed a single text string.

        Args:
            text: The text to embed
            model: Optional specific model to use (defaults to self.model_name)
            encoding_format: Format of the embedding (default: float)
            dimensions: Vector dimensions (defaults to self.vector_dimensions)

        Returns:
            List of embedding values
        """
        pass

    @abstractmethod
    async def embed_many(
        self,
        texts: List[str],
        model: Optional[str] = None,
        encoding_format: str = "float",
        dimensions: Optional[int] = None,
    ) -> List[List[float]]:
        """Embed multiple text strings.

        Args:
            texts: List of texts to embed
            model: Optional specific model to use (defaults to self.model_name)
            encoding_format: Format of the embedding (default: float)
            dimensions: Vector dimensions (defaults to self.vector_dimensions)

        Returns:
            List of embedding vectors
        """
        pass
