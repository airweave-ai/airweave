"""Base tokenizer protocol and interface."""

from abc import ABC, abstractmethod
from typing import List, Sequence, Union


class BaseTokenizer(ABC):
    """Abstract base class for all tokenizer implementations.

    Provides a unified interface for token encoding/decoding across different
    tokenizer backends (tiktoken, mistral_common, etc.).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the tokenizer name/identifier."""
        pass

    @abstractmethod
    def encode(self, text: str, **kwargs) -> List[int]:
        """Encode text to token IDs.

        Args:
            text: Text string to encode
            **kwargs: Implementation-specific options (for library compatibility)

        Returns:
            List of token IDs
        """
        pass

    @abstractmethod
    def decode(self, tokens: Sequence[int]) -> str:
        """Decode token IDs back to text.

        Args:
            tokens: Sequence of token IDs

        Returns:
            Decoded text string
        """
        pass

    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in text.

        Args:
            text: Text string to count tokens in

        Returns:
            Number of tokens
        """
        return len(self.encode(text))

    def encode_batch(self, texts: List[str]) -> List[List[int]]:
        """Encode multiple texts to token IDs.

        Args:
            texts: List of text strings to encode

        Returns:
            List of token ID lists
        """
        return [self.encode(text) for text in texts]

    def decode_batch(self, token_lists: List[List[int]]) -> List[str]:
        """Decode multiple token ID lists back to text.

        Args:
            token_lists: List of token ID lists

        Returns:
            List of decoded text strings
        """
        return [self.decode(tokens) for tokens in token_lists]

    def tokenize(self, text: str) -> Sequence[Union[str, int]]:
        """Alias for encode() - for compatibility with some libraries.

        Args:
            text: Text string to tokenize

        Returns:
            Sequence of token IDs
        """
        return self.encode(text)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
