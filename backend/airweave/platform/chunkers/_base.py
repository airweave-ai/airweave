"""Base chunker interface for all chunker implementations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseChunker(ABC):
    """Interface for all chunker implementations.

    Chunkers must implement async batch processing for compatibility
    with entity pipeline's concurrent worker model.
    """

    @abstractmethod
    async def chunk_batch(self, texts: List[str]) -> List[List[Dict[str, Any]]]:
        """Chunk a batch of texts asynchronously.

        Args:
            texts: List of textual representations to chunk

        Returns:
            List of chunk lists, where each chunk dict contains:
            {
                "text": str,           # Chunk text content
                "start_index": int,    # Start position in original text
                "end_index": int,      # End position in original text
                "token_count": int     # Number of tokens (cl100k_base tokenizer)
            }

        Raises:
            SyncFailureError: If critical system error occurs (model loading, etc.)
        """
        pass
