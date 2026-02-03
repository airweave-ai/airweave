"""TikToken tokenizer implementation for spotlight search.

Uses OpenAI's tiktoken library for fast BPE tokenization.
This is a local operation - no network calls, no rate limiting needed.
"""

import tiktoken

from airweave.search.spotlight.external.tokenizer.registry import TokenizerEncoding


class TiktokenTokenizer:
    """TikToken-based tokenizer for spotlight search.

    Simple wrapper around tiktoken that implements the SpotlightTokenizerInterface.
    Only provides token counting - the planner doesn't need encode/decode.
    """

    def __init__(self, encoding: TokenizerEncoding) -> None:
        """Initialize with a tokenizer encoding.

        Args:
            encoding: The TokenizerEncoding enum (value is the tiktoken encoding name).

        Raises:
            ValueError: If tiktoken cannot load the encoding.
        """
        self._encoding_enum = encoding

        try:
            self._tiktoken = tiktoken.get_encoding(encoding.value)
        except Exception as e:
            raise ValueError(f"Failed to load tiktoken encoding '{encoding.value}': {e}") from e

    @property
    def encoding(self) -> TokenizerEncoding:
        """The tokenizer encoding this instance uses."""
        return self._encoding_enum

    def count_tokens(self, text: str) -> int:
        """Count tokens in text.

        Uses allowed_special="all" to handle special tokens like <|endoftext|>
        that may appear in user content without raising errors.

        Args:
            text: The text to tokenize.

        Returns:
            Number of tokens.
        """
        if not text:
            return 0

        # allowed_special="all" ensures we don't raise on special tokens
        # that might appear in user content
        return len(self._tiktoken.encode(text, allowed_special="all"))
