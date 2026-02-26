"""Tokenizer interface for agentic search."""

from typing import Protocol

from airweave.search.agentic_search.external.tokenizer.registry import TokenizerModelSpec


class AgenticSearchTokenizerInterface(Protocol):
    """Tokenizer interface for agentic search.

    Minimal interface - the planner only needs to count tokens.
    """

    @property
    def model_spec(self) -> TokenizerModelSpec:
        """Get the model specification."""
        ...

    def count_tokens(self, text: str) -> int:
        """Count tokens in text.

        Args:
            text: The text to tokenize.

        Returns:
            Number of tokens.
        """
        ...
