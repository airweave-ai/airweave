"""Tiktoken compatibility wrapper for Chonkie.

This module provides a wrapper around tiktoken encodings that allows special tokens
(like <|endoftext|>) to be encoded without errors.

IMPORTANT: This file MUST be named with "tiktoken" in the path because Chonkie's
AutoTokenizer._get_backend() detects the tokenizer backend by checking:

    if "tiktoken" in str(type(tokenizer)):
        return "tiktoken"

By placing our wrapper in a module named tiktoken_compat.py, the type string becomes:
    <class 'airweave.platform.chunkers.tiktoken_compat.SafeEncoding'>

which contains "tiktoken" and passes Chonkie's backend detection.
"""

from typing import List, Sequence


class SafeEncoding:
    """Wrapper that forces allowed_special='all' on tiktoken encoding.

    This wrapper is needed because Chonkie calls the encoding's encode() method
    directly, bypassing our TikTokenTokenizer wrapper. Without this, special
    tokens like <|endoftext|> in code comments/strings cause encoding failures.

    Example special tokens that may appear in user content:
    - <|endoftext|> (AI-generated text pasted into docs/Linear)
    - <|fim_prefix|>, <|fim_suffix|>, <|fim_middle|> (Codex FIM tokens)
    """

    def __init__(self, encoding):
        """Initialize the wrapper with a tiktoken encoding.

        Args:
            encoding: A tiktoken.Encoding instance
        """
        self._encoding = encoding
        # Copy attributes that Chonkie might check
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

    # Delegate attribute access to underlying encoding for compatibility
    def __getattr__(self, name):
        """Delegate attribute access to underlying encoding."""
        return getattr(self._encoding, name)
