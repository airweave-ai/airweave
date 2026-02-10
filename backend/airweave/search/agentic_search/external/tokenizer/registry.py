"""Tokenizer model registry.

Centralizes knowledge about available tokenizer models and their capabilities.
"""

from dataclasses import dataclass

from airweave.search.agentic_search.config import TokenizerEncoding, TokenizerType


@dataclass(frozen=True)
class TokenizerModelSpec:
    """Specification for a tokenizer model.

    Attributes:
        encoding_name: The encoding name string to pass to the tokenizer library
                       (e.g., "o200k_harmony" for tiktoken).
    """

    encoding_name: str


# Registry of all encodings by tokenizer type
TOKENIZER_REGISTRY: dict[TokenizerType, dict[TokenizerEncoding, TokenizerModelSpec]] = {
    TokenizerType.TIKTOKEN: {
        TokenizerEncoding.O200K_HARMONY: TokenizerModelSpec(
            encoding_name="o200k_harmony",
        ),
    },
}


def get_model_spec(
    tokenizer_type: TokenizerType,
    encoding: TokenizerEncoding,
) -> TokenizerModelSpec:
    """Get tokenizer model spec with validation.

    Args:
        tokenizer_type: The tokenizer implementation.
        encoding: The encoding to use.

    Returns:
        TokenizerModelSpec for the type/encoding combination.

    Raises:
        ValueError: If tokenizer type is not in the registry.
        ValueError: If encoding is not supported by the tokenizer type.
    """
    if tokenizer_type not in TOKENIZER_REGISTRY:
        raise ValueError(f"Unknown tokenizer type: {tokenizer_type.value}")

    type_encodings = TOKENIZER_REGISTRY[tokenizer_type]
    if encoding not in type_encodings:
        available = [e.value for e in type_encodings.keys()]
        raise ValueError(
            f"Encoding '{encoding.value}' not supported by {tokenizer_type.value}. "
            f"Available: {available}"
        )

    return type_encodings[encoding]
