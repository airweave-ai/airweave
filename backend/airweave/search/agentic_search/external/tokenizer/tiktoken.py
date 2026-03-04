"""TikToken tokenizer implementation for agentic search.

Uses OpenAI's tiktoken library for fast BPE tokenization.
This is a local operation - no network calls, no rate limiting needed.
"""

import tiktoken

from airweave.search.agentic_search.external.tokenizer.registry import TokenizerModelSpec


class TiktokenTokenizer:
    """TikToken-based tokenizer for agentic search.

    Simple wrapper around tiktoken that implements the AgenticSearchTokenizerInterface.
    Only provides token counting - the planner doesn't need encode/decode.
    """

    def __init__(self, model_spec: TokenizerModelSpec) -> None:
        """Initialize with a tokenizer model spec.

        Args:
            model_spec: Model specification from the registry.

        Raises:
            RuntimeError: If tiktoken cannot load the encoding.
        """
        self._model_spec = model_spec

        try:
            self._tiktoken = tiktoken.get_encoding(model_spec.encoding_name)
        except Exception as e:
            raise RuntimeError(
                f"Failed to load tiktoken encoding '{model_spec.encoding_name}': {e}"
            ) from e

    @property
    def model_spec(self) -> TokenizerModelSpec:
        """Get the model specification."""
        return self._model_spec

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
