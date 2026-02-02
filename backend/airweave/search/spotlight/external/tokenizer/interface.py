"""Tokenizer interface for spotlight search."""

from typing import Protocol

from airweave.search.spotlight.external.llm.registry import TokenizerEncoding


class SpotlightTokenizerInterface(Protocol):
    """Tokenizer interface for spotlight search."""

    @property
    def encoding(self) -> TokenizerEncoding:
        """The tokenizer encoding this instance uses."""
        ...

    def count_tokens(self, text: str) -> int:
        """Count tokens in text.

        Args:
            text: The text to tokenize.

        Returns:
            Number of tokens.
        """
        ...
