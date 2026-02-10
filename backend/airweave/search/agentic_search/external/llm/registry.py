"""Model registry for agentic search.

Defines valid provider-model combinations and their specifications.
"""

from dataclasses import dataclass
from typing import Union

from airweave.search.agentic_search.config import (
    LLMModel,
    LLMProvider,
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
class LLMModelSpec:
    """Immutable specification for an LLM model.

    frozen=True makes this hashable and prevents accidental mutation.

    Attributes:
        api_model_name: The model name string to use in API calls (e.g., "gpt-oss-120b").
        context_window: Maximum tokens the model can process (input + reasoning + output).
        max_output_tokens: Maximum tokens the model can generate.
        required_tokenizer_type: The tokenizer type this model requires.
        required_tokenizer_encoding: The encoding this model requires.
        rate_limit_rpm: Requests per minute limit.
        rate_limit_tpm: Tokens per minute limit.
        reasoning: Model-specific reasoning configuration (None if model doesn't support it).
    """

    api_model_name: str
    context_window: int
    max_output_tokens: int
    required_tokenizer_type: TokenizerType
    required_tokenizer_encoding: TokenizerEncoding
    rate_limit_rpm: int
    rate_limit_tpm: int
    reasoning: ReasoningConfig


# Registry: provider -> model -> spec
#
# Each LLMModel must appear under exactly one provider. The model name is the
# unique identifier used by resolve_provider_for_model() to determine which
# provider to instantiate. If you need the same underlying model on two
# providers, create distinct LLMModel entries (e.g. GPT_OSS_120B_CEREBRAS).
MODEL_REGISTRY: dict[LLMProvider, dict[LLMModel, LLMModelSpec]] = {
    LLMProvider.CEREBRAS: {
        LLMModel.GPT_OSS_120B: LLMModelSpec(
            api_model_name="gpt-oss-120b",
            context_window=131_000,
            max_output_tokens=40_000,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            rate_limit_rpm=1_000,
            rate_limit_tpm=1_000_000,
            reasoning=ReasoningConfig(
                param_name="reasoning_effort",
                param_value="high",
            ),
        ),
        LLMModel.ZAI_GLM_4_7: LLMModelSpec(
            api_model_name="zai-glm-4.7",
            context_window=131_000,
            max_output_tokens=40_000,
            # Using tiktoken o200k_harmony as approximation — the actual GLM tokenizer
            # isn't publicly documented, but since we only use it for token counting
            # (budget estimation), a close approximation is sufficient.
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            rate_limit_rpm=500,
            rate_limit_tpm=500_000,
            # GLM reasoning is enabled by default. disable_reasoning=False keeps it on.
            reasoning=ReasoningConfig(
                param_name="disable_reasoning",
                param_value=False,
            ),
        ),
    },
}


def resolve_provider_for_model(model: LLMModel) -> LLMProvider:
    """Resolve which provider hosts a given model.

    Each model is unique across providers, so this is an unambiguous reverse lookup.

    Args:
        model: The LLM model to look up.

    Returns:
        The LLMProvider that hosts this model.

    Raises:
        ValueError: If the model is not found in any provider.
    """
    for provider, models in MODEL_REGISTRY.items():
        if model in models:
            return provider

    all_models = [m.value for p in MODEL_REGISTRY.values() for m in p.keys()]
    raise ValueError(f"Model '{model.value}' not found in any provider. Available: {all_models}")


def get_model_spec(provider: LLMProvider, model: LLMModel) -> LLMModelSpec:
    """Get model spec with validation.

    Args:
        provider: The LLM provider.
        model: The model name.

    Returns:
        LLMModelSpec for the provider/model combination.

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


def get_available_models(provider: LLMProvider) -> list[LLMModel]:
    """Get list of models available for a provider.

    Args:
        provider: The LLM provider.

    Returns:
        List of LLMModel enums available for this provider.
    """
    if provider not in MODEL_REGISTRY:
        raise ValueError(f"Unknown provider: {provider}")
    return list(MODEL_REGISTRY[provider].keys())
