"""Model registry for spotlight search.

Single source of truth for provider-model relationships and model specifications.
All identifiers are enums for type safety.
"""

from dataclasses import dataclass
from enum import Enum


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    CEREBRAS = "cerebras"


class ModelName(str, Enum):
    """Supported model names (global across providers)."""

    GPT_OSS_120B = "gpt-oss-120b"


class TokenizerEncoding(str, Enum):
    """Supported tokenizer encodings."""

    O200K_HARMONY = "o200k_harmony"


@dataclass(frozen=True)
class ModelSpec:
    """Immutable specification for a model.

    frozen=True makes this hashable and prevents accidental mutation.

    Attributes:
        context_window: Maximum tokens the model can process (input + reasoning + output).
        max_output_tokens: Maximum tokens the model can generate.
        tokenizer_encoding: The tokenizer encoding this model requires.
        rate_limit_rpm: Requests per minute limit.
        rate_limit_tpm: Tokens per minute limit.
    """

    context_window: int
    max_output_tokens: int
    tokenizer_encoding: TokenizerEncoding
    rate_limit_rpm: int
    rate_limit_tpm: int


# Registry: provider -> model -> spec
MODEL_REGISTRY: dict[LLMProvider, dict[ModelName, ModelSpec]] = {
    LLMProvider.CEREBRAS: {
        ModelName.GPT_OSS_120B: ModelSpec(
            context_window=131_000,
            max_output_tokens=40_000,
            tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            rate_limit_rpm=1_000,
            rate_limit_tpm=1_000_000,
        ),
    },
}


def get_model_spec(provider: LLMProvider, model: ModelName) -> ModelSpec:
    """Get model spec with validation.

    Args:
        provider: The LLM provider.
        model: The model name.

    Returns:
        ModelSpec for the provider/model combination.

    Raises:
        ValueError: If provider doesn't support the model.
    """
    if provider not in MODEL_REGISTRY:
        raise ValueError(f"Unknown provider: {provider}")

    provider_models = MODEL_REGISTRY[provider]
    if model not in provider_models:
        available = [m.value for m in provider_models.keys()]
        raise ValueError(
            f"Model '{model.value}' not supported by {provider.value}. Available: {available}"
        )

    return provider_models[model]


def get_available_models(provider: LLMProvider) -> list[ModelName]:
    """Get list of models available for a provider.

    Args:
        provider: The LLM provider.

    Returns:
        List of ModelName enums available for this provider.
    """
    if provider not in MODEL_REGISTRY:
        raise ValueError(f"Unknown provider: {provider}")
    return list(MODEL_REGISTRY[provider].keys())
