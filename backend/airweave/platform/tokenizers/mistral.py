"""Mistral tokenizer implementation using mistral_common."""

from typing import Any, List, Optional, Sequence

from ._base import BaseTokenizer

# Lazy import to avoid hard dependency
_MistralTokenizer = None


def _get_mistral_tokenizer_class():
    """Lazy load MistralTokenizer to avoid import errors if not installed."""
    global _MistralTokenizer
    if _MistralTokenizer is None:
        try:
            from mistral_common.tokens.tokenizers.mistral import (
                MistralTokenizer as MT,
            )

            _MistralTokenizer = MT
        except ImportError:
            raise RuntimeError(
                "mistral_common is required for Mistral tokenization. "
                "Install with: pip install mistral_common"
            )
    return _MistralTokenizer


def is_mistral_tokenizer(name: str) -> bool:
    """Check if a name is a Mistral tokenizer."""
    return bool(name) and name.lower().startswith("mistral")


class MistralTokenizer(BaseTokenizer):
    """Mistral tokenizer using mistral_common's built-in tokenizers.

    Uses the built-in v3 (Tekken) tokenizer which covers all current Mistral models.
    No downloads required - tokenizer vocabulary is bundled with mistral_common.
    """

    def __init__(self, model_name: Optional[str] = None):
        """Initialize Mistral tokenizer.

        Args:
            model_name: Model name (for identification only, tokenizer is built-in)

        Raises:
            RuntimeError: If mistral_common is not installed
        """
        self._name = model_name or "mistral-v3"
        self._tokenizer = self._load_tokenizer()

    @property
    def name(self) -> str:
        """Return the tokenizer name."""
        return self._name

    def _load_tokenizer(self) -> Any:
        """Load the built-in Mistral tokenizer.

        Uses v3 (Tekken) if available, falls back to v1.
        No network requests - vocabulary is bundled with mistral_common.
        """
        MistralTokenizerClass = _get_mistral_tokenizer_class()

        # Prefer v3 (Tekken) - modern tokenizer for current models
        if hasattr(MistralTokenizerClass, "v3"):
            return MistralTokenizerClass.v3()

        # Fall back to v1 for older mistral_common versions
        if hasattr(MistralTokenizerClass, "v1"):
            return MistralTokenizerClass.v1()

        return MistralTokenizerClass()

    def _get_inner_tokenizer(self) -> Any:
        """Get the inner tokenizer that has encode/decode methods."""
        tokenizer = self._tokenizer

        # MistralTokenizer wraps an instruct_tokenizer which wraps the actual tokenizer
        if hasattr(tokenizer, "instruct_tokenizer"):
            inner = tokenizer.instruct_tokenizer
            if hasattr(inner, "tokenizer"):
                return inner.tokenizer
            return inner

        return tokenizer

    def encode(self, text: str, **kwargs) -> List[int]:
        """Encode text to token IDs.

        Args:
            text: Text string to encode
            **kwargs: Ignored (for compatibility with other tokenizer interfaces)

        Returns:
            List of token IDs
        """
        inner = self._get_inner_tokenizer()

        # Try encode with various signatures
        if hasattr(inner, "encode"):
            try:
                result = inner.encode(text, bos=False, eos=False)
                return self._extract_ids(result)
            except TypeError:
                pass
            try:
                result = inner.encode(text)
                return self._extract_ids(result)
            except TypeError:
                pass

        raise TypeError(f"Cannot encode with Mistral tokenizer {self._name}")

    def _extract_ids(self, result: Any) -> List[int]:
        """Extract token IDs from tokenizer result."""
        if hasattr(result, "tokens"):
            return list(result.tokens)
        if hasattr(result, "ids"):
            return list(result.ids)
        if isinstance(result, list):
            return result
        return list(result)

    def decode(self, tokens: Sequence[int]) -> str:
        """Decode token IDs back to text.

        Args:
            tokens: Sequence of token IDs

        Returns:
            Decoded text string
        """
        inner = self._get_inner_tokenizer()

        if hasattr(inner, "decode"):
            return inner.decode(list(tokens))

        raise NotImplementedError(f"Decode not supported for {self._name}")
