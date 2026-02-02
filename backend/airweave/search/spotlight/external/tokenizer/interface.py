"""Tokenizer interface for spotlight search."""

from typing import Protocol

from airweave.search.spotlight.external.tokenizer.registry import TokenizerEncoding


class SpotlightTokenizerInterface(Protocol):
    """Tokenizer interface for spotlight search.

    Minimal interface - the planner only needs to count tokens.
    """

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
