"""Model registry for spotlight search.

Defines valid provider-model combinations and their specifications.
"""

from dataclasses import dataclass
from typing import Union

from airweave.search.spotlight.config import LLMProvider, ModelName
from airweave.search.spotlight.external.tokenizer.registry import (
    TokenizerEncoding,
    TokenizerType,
)


@dataclass(frozen=True)
class ReasoningConfig:
    """Model-specific reasoning configuration.

    Different models have different parameters for controlling reasoning:
    - GPT-OSS: reasoning_effort="low"|"medium"|"high"
    - GLM/Qwen: disable_reasoning=True|False

    This dataclass encapsulates the parameter name and value so the provider
    can pass it through without knowing about model families.

    Attributes:
        param_name: The API parameter name (e.g., "reasoning_effort", "disable_reasoning").
        param_value: The value to pass (e.g., "medium", False).
    """

    param_name: str
    param_value: Union[str, bool]


@dataclass(frozen=True)
class ModelSpec:
    """Immutable specification for a model.

    frozen=True makes this hashable and prevents accidental mutation.

    Attributes:
        api_model_name: The model name string to use in API calls (e.g., "gpt-oss-120b").
        context_window: Maximum tokens the model can process (input + reasoning + output).
        max_output_tokens: Maximum tokens the model can generate.
        tokenizer_type: Which tokenizer library to use.
        tokenizer_encoding: Which encoding to use (must be supported by tokenizer_type).
        rate_limit_rpm: Requests per minute limit.
        rate_limit_tpm: Tokens per minute limit.
        reasoning: Model-specific reasoning configuration (None if model doesn't support it).
    """

    api_model_name: str
    context_window: int
    max_output_tokens: int
    tokenizer_type: TokenizerType
    tokenizer_encoding: TokenizerEncoding
    rate_limit_rpm: int
    rate_limit_tpm: int
    reasoning: ReasoningConfig


# Registry: provider -> model -> spec
MODEL_REGISTRY: dict[LLMProvider, dict[ModelName, ModelSpec]] = {
    LLMProvider.CEREBRAS: {
        ModelName.GPT_OSS_120B: ModelSpec(
            api_model_name="gpt-oss-120b",
            context_window=131_000,
            max_output_tokens=40_000,
            tokenizer_type=TokenizerType.TIKTOKEN,
            tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            rate_limit_rpm=1_000,
            rate_limit_tpm=1_000_000,
            reasoning=ReasoningConfig(
                param_name="reasoning_effort",
                param_value="medium",
            ),
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
