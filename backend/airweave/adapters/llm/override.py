"""LLM model override utility for eval/admin endpoints.

Parses a 'provider/model' string and creates a single-provider LLM instance,
bypassing the container's shared fallback chain.
"""

from airweave.adapters.llm.anthropic import AnthropicLLM
from airweave.adapters.llm.cerebras import CerebrasLLM
from airweave.adapters.llm.groq import GroqLLM
from airweave.adapters.llm.registry import (
    LLMModel,
    LLMProvider,
    get_model_spec,
)
from airweave.adapters.llm.together import TogetherLLM
from airweave.core.protocols.llm import LLMProtocol

_PROVIDER_CLASSES = {
    LLMProvider.ANTHROPIC: AnthropicLLM,
    LLMProvider.CEREBRAS: CerebrasLLM,
    LLMProvider.GROQ: GroqLLM,
    LLMProvider.TOGETHER: TogetherLLM,
}


def create_llm_from_override(model_override: str) -> LLMProtocol:
    """Parse 'provider/model' string and create a single-provider LLM instance.

    Args:
        model_override: String in format 'provider/model',
            e.g. 'together/zai-glm-5-thinking' or 'anthropic/claude-sonnet-4.6'.

    Returns:
        A fresh LLM instance (not the container singleton).

    Raises:
        ValueError: If provider or model is unknown.
    """
    parts = model_override.split("/", 1)
    if len(parts) != 2:
        raise ValueError(
            f"Invalid model override format: '{model_override}'. "
            f"Expected 'provider/model' (e.g. 'together/zai-glm-5-thinking')."
        )

    provider_str, model_str = parts

    try:
        provider = LLMProvider(provider_str)
    except ValueError:
        valid = [p.value for p in LLMProvider]
        raise ValueError(
            f"Unknown provider: '{provider_str}'. Valid providers: {valid}"
        )

    try:
        model = LLMModel(model_str)
    except ValueError:
        valid = [m.value for m in LLMModel]
        raise ValueError(
            f"Unknown model: '{model_str}'. Valid models: {valid}"
        )

    model_spec = get_model_spec(provider, model)

    provider_cls = _PROVIDER_CLASSES.get(provider)
    if provider_cls is None:
        raise ValueError(f"No LLM class registered for provider: {provider.value}")

    # No fallback chain wrapping this provider, so use default retries
    return provider_cls(model_spec=model_spec)
