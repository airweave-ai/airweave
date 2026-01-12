"""Base embedder interface for all embedder implementations."""

from abc import ABC, abstractmethod
from typing import List, Optional

from fastembed import SparseEmbedding

from airweave.platform.contexts import SyncContext


class BaseEmbedder(ABC):
    """Base class for singleton embedders shared across pod.

    All embedders must implement async batch processing.
    Embedders never skip entities - any failure raises SyncFailureError.
    """

    _instance: Optional["BaseEmbedder"] = None

    def __new__(cls):
        """Singleton pattern - one instance per pod."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    @abstractmethod
    async def embed_many(
        self, texts: List[str], sync_context: SyncContext
    ) -> List[List[float]] | List[SparseEmbedding]:
        """Embed batch of texts.

        Args:
            texts: List of text strings to embed (never empty)
            sync_context: Sync context with logger

        Returns:
            List of embeddings (exactly len(texts), no None values)

        Raises:
            SyncFailureError: On any failure (API errors, empty texts, etc.)
        """
        pass
