"""TikToken tokenizer implementation.

NOTE: This module is intentionally named 'tiktoken.py' so that Chonkie's
AutoTokenizer._get_backend() detects it as tiktoken via:
    if "tiktoken" in str(type(self.tokenizer))
"""

from typing import List, Sequence, Union

import tiktoken
from tiktoken import Encoding

from ._base import BaseTokenizer

# Standard tiktoken encoding names
TIKTOKEN_ENCODINGS = {
    "cl100k_base",  # GPT-4, GPT-3.5-turbo, text-embedding-ada-002, text-embedding-3-*
    "o200k_base",  # GPT-4o
    "p50k_base",  # Codex models
    "p50k_edit",  # text-davinci-edit-001, code-davinci-edit-001
    "r50k_base",  # GPT-3 (davinci, curie, babbage, ada)
    "gpt2",  # GPT-2
}


class TikTokenTokenizer(BaseTokenizer):
    """TikToken-based tokenizer compatible with Chonkie.

    Wraps tiktoken Encoding to handle special tokens like <|endoftext|>
    that may appear in user content. The module path contains "tiktoken"
    so Chonkie detects this as a tiktoken backend.
    """

    def __init__(self, encoding_name: str = "cl100k_base"):
        """Initialize with a tiktoken encoding.

        Args:
            encoding_name: Name of the tiktoken encoding (e.g., "cl100k_base")

        Raises:
            ValueError: If tiktoken can't load the encoding
        """
        self._name = encoding_name
        try:
            self._encoding: Encoding = tiktoken.get_encoding(encoding_name)
        except Exception as e:
            raise ValueError(
                f"Failed to load tiktoken encoding '{encoding_name}': {e}. "
                f"Standard encodings: {sorted(TIKTOKEN_ENCODINGS)}"
            ) from e

    @property
    def name(self) -> str:
        """Return the encoding name."""
        return self._name

    @property
    def encoding(self) -> Encoding:
        """Return the underlying tiktoken Encoding object."""
        return self._encoding

    def encode(self, text: str, **kwargs) -> List[int]:
        """Encode text to token IDs, allowing all special tokens.

        Args:
            text: Text string to encode
            **kwargs: Ignored (for Chonkie compatibility)

        Returns:
            List of token IDs
        """
        return self._encoding.encode(text, allowed_special="all")

    def decode(self, tokens: Sequence[int]) -> str:
        """Decode token IDs back to text."""
        return self._encoding.decode(list(tokens))

    def encode_batch(self, texts: List[str]) -> List[List[int]]:
        """Encode multiple texts to token IDs."""
        return [self._encoding.encode(text, allowed_special="all") for text in texts]

    def decode_batch(self, token_lists: List[List[int]]) -> List[str]:
        """Decode multiple token sequences back to text."""
        return [self._encoding.decode(tokens) for tokens in token_lists]

    def tokenize(self, text: str) -> Sequence[Union[str, int]]:
        """Alias for encode() - for Chonkie compatibility."""
        return self.encode(text)


def is_tiktoken_encoding(name: str) -> bool:
    """Check if a name is a known tiktoken encoding.

    Note: This only checks against standard encodings. Custom encodings
    may still be valid if tiktoken can load them.

    Args:
        name: Encoding name to check

    Returns:
        True if name is a known standard tiktoken encoding
    """
    return name in TIKTOKEN_ENCODINGS
