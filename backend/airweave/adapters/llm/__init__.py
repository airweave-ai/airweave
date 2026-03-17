"""LLM adapters."""

from airweave.adapters.llm.anthropic import AnthropicLLM
from airweave.adapters.llm.base import BaseLLM
from airweave.adapters.llm.cerebras import CerebrasLLM
from airweave.adapters.llm.exceptions import (
    LLMAllProvidersFailedError,
    LLMError,
    LLMFatalError,
    LLMProviderExhaustedError,
    LLMTransientError,
)
from airweave.adapters.llm.fallback import FallbackChainLLM
from airweave.adapters.llm.groq import GroqLLM
from airweave.adapters.llm.registry import (
    MODEL_REGISTRY,
    PROVIDER_API_KEY_SETTINGS,
    LLMModel,
    LLMModelSpec,
    LLMProvider,
    ReasoningConfig,
    get_available_models,
    get_model_spec,
)
from airweave.adapters.llm.together import TogetherLLM
from airweave.adapters.llm.tool_response import LLMResponse, LLMToolCall
from airweave.core.protocols.llm import LLMProtocol

__all__ = [
    # Protocol
    "LLMProtocol",
    # Base + providers
    "BaseLLM",
    "AnthropicLLM",
    "CerebrasLLM",
    "GroqLLM",
    "TogetherLLM",
    "FallbackChainLLM",
    # Exceptions
    "LLMError",
    "LLMTransientError",
    "LLMFatalError",
    "LLMProviderExhaustedError",
    "LLMAllProvidersFailedError",
    # Enums
    "LLMProvider",
    "LLMModel",
    # Types
    "LLMModelSpec",
    "ReasoningConfig",
    "LLMToolCall",
    "LLMResponse",
    # Registry
    "MODEL_REGISTRY",
    "PROVIDER_API_KEY_SETTINGS",
    "get_model_spec",
    "get_available_models",
]
