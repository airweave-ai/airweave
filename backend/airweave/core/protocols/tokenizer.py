"""Tokenizer provider protocol.

Defines the structural typing contract that any tokenizer backend must satisfy.
Uses :class:`typing.Protocol` so implementations don't need to inherit.

Usage::

    from airweave.core.protocols.tokenizer import TokenizerProtocol


    def build_search(tokenizer: TokenizerProtocol) -> ...:
        count = tokenizer.count_tokens(text)
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class TokenizerProtocol(Protocol):
    """Structural protocol for tokenizer providers.

    Any class that implements these methods with matching signatures is
    considered a valid tokenizer provider -- no subclassing required.
    """

    @property
    def model_spec(self) -> Any:
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
