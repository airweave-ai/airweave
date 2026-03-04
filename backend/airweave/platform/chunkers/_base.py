"""Base chunker interface for all chunker implementations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Sequence

__all__ = ["BaseChunker", "SafeTiktokenEncoding"]


class SafeTiktokenEncoding:
    """Wrapper that forces allowed_special='all' on tiktoken encoding.

    This is needed because Chonkie calls the encoding's encode() method directly,
    bypassing our TikTokenTokenizer wrapper. Without this, special tokens like
    <|endoftext|> in code comments/strings cause encoding failures.

    Example special tokens that may appear in user content:
    - <|endoftext|> (AI-generated text pasted into docs/Linear)
    - <|fim_prefix|>, <|fim_suffix|>, <|fim_middle|> (Codex FIM tokens)
    """

    def __init__(self, encoding):
        self._encoding = encoding
        # Copy attributes that Chonkie's AutoTokenizer checks for backend detection
        self.name = getattr(encoding, "name", "cl100k_base")

    def encode(self, text: str, **kwargs) -> List[int]:
        """Encode text, allowing all special tokens."""
        kwargs.setdefault("allowed_special", "all")
        return self._encoding.encode(text, **kwargs)

    def decode(self, tokens: Sequence[int]) -> str:
        """Decode tokens back to text."""
        return self._encoding.decode(list(tokens))

    def encode_batch(self, texts: List[str], **kwargs) -> List[List[int]]:
        """Encode multiple texts."""
        kwargs.setdefault("allowed_special", "all")
        return [self._encoding.encode(text, **kwargs) for text in texts]

    def decode_batch(self, token_lists: List[List[int]]) -> List[str]:
        """Decode multiple token sequences."""
        return [self._encoding.decode(tokens) for tokens in token_lists]

    # Delegate attribute access to underlying encoding for Chonkie compatibility
    def __getattr__(self, name):
        return getattr(self._encoding, name)


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
