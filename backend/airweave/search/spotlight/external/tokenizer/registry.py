"""Tokenizer registry for spotlight search.

Defines available tokenizer types, encodings, and which encodings each type supports.
"""

from enum import Enum


class TokenizerType(str, Enum):
    """Tokenizer implementations."""

    TIKTOKEN = "tiktoken"


class TokenizerEncoding(str, Enum):
    """Tokenizer encodings."""

    O200K_HARMONY = "o200k_harmony"


# Which encodings each tokenizer type supports
SUPPORTED_ENCODINGS: dict[TokenizerType, set[TokenizerEncoding]] = {
    TokenizerType.TIKTOKEN: {
        TokenizerEncoding.O200K_HARMONY,
    },
}


def is_encoding_supported(tokenizer_type: TokenizerType, encoding: TokenizerEncoding) -> bool:
    """Check if a tokenizer type supports an encoding.

    Args:
        tokenizer_type: The tokenizer implementation.
        encoding: The encoding to check.

    Returns:
        True if the tokenizer supports the encoding.
    """
    supported = SUPPORTED_ENCODINGS.get(tokenizer_type, set())
    return encoding in supported
