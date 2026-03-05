"""Tokenizer factory with caching."""

from ._base import BaseTokenizer
from .mistral import MistralTokenizer, is_mistral_tokenizer
from .tiktoken import TIKTOKEN_ENCODINGS, TikTokenTokenizer, is_tiktoken_encoding

# Cache tokenizer instances (stateless and reusable)
_cache: dict[str, BaseTokenizer] = {}


def get_tokenizer(name: str) -> BaseTokenizer:
    """Get a tokenizer by name.

    Args:
        name: Tokenizer name (e.g., "cl100k_base", "mistral-embed")

    Returns:
        Tokenizer instance

    Raises:
        ValueError: If tokenizer name is not recognized
    """
    if name in _cache:
        return _cache[name]

    if is_tiktoken_encoding(name):
        tokenizer = TikTokenTokenizer(name)
    elif is_mistral_tokenizer(name):
        tokenizer = MistralTokenizer(name)
    else:
        # Try tiktoken as fallback
        try:
            tokenizer = TikTokenTokenizer(name)
        except ValueError:
            raise ValueError(
                f"Unknown tokenizer: {name}. "
                f"Valid: {sorted(TIKTOKEN_ENCODINGS)} or names starting with 'mistral'."
            )

    _cache[name] = tokenizer
    return tokenizer
