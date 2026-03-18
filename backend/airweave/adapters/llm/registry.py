"""Model registry for LLM adapters.

Single source of truth for all provider-model combinations and their specifications.
The fallback chain (which combinations to use and in what order) is configured in
SearchConfig, not here. This module is purely a catalog.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Union

from airweave.adapters.tokenizer.registry import TokenizerEncoding, TokenizerType


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    CEREBRAS = "cerebras"
    GROQ = "groq"
    ANTHROPIC = "anthropic"
    TOGETHER = "together"


class LLMModel(str, Enum):
    """Supported LLM models (global across providers).

    A model can be hosted by multiple providers (e.g., GPT_OSS_120B on both
    Cerebras and Groq). The MODEL_REGISTRY maps each (provider, model) pair
    to its provider-specific specification.
    """

    GPT_OSS_120B = "gpt-oss-120b"
    ZAI_GLM_4_7 = "zai-glm-4.7"
    ZAI_GLM_5 = "zai-glm-5"
    ZAI_GLM_5_THINKING = "zai-glm-5-thinking"
    CLAUDE_SONNET_4_5 = "claude-sonnet-4.5"
    CLAUDE_SONNET_4_6 = "claude-sonnet-4.6"
    CLAUDE_SONNET_4_6_THINKING = "claude-sonnet-4.6-thinking"
    KIMI_K2_5 = "kimi-k2.5"
    KIMI_K2_5_THINKING = "kimi-k2.5-thinking"
    QWEN_3_5 = "qwen-3.5"
    QWEN_3_5_THINKING = "qwen-3.5-thinking"
    QWEN_3_5_DEDICATED = "qwen-3.5-dedicated"
    QWEN_3_5_DEDICATED_THINKING = "qwen-3.5-dedicated-thinking"
    ZAI_GLM_5_DEDICATED = "zai-glm-5-dedicated"
    ZAI_GLM_5_DEDICATED_THINKING = "zai-glm-5-dedicated-thinking"
    MINIMAX_M2_5 = "minimax-m2.5"
    MINIMAX_M2_5_THINKING = "minimax-m2.5-thinking"


@dataclass(frozen=True)
class ThinkingConfig:
    """Model-specific thinking/reasoning API configuration.

    Different models have different parameters for controlling thinking:
    - GPT-OSS: reasoning_effort="low"|"medium"|"high"
    - GLM/Qwen: disable_reasoning=True|False
    - Anthropic 4.6: adaptive thinking with effort="high"
    - Anthropic 4.5: no thinking (param_name="_noop")

    This dataclass encapsulates the parameter name and value so the provider
    can pass it through without knowing about model families.
    """

    param_name: str
    param_value: Union[str, bool, int]
    effort: str | None = None


# Backwards compat alias
ReasoningConfig = ThinkingConfig


@dataclass(frozen=True)
class LLMModelSpec:
    """Immutable specification for an LLM model.

    frozen=True makes this hashable and prevents accidental mutation.
    """

    api_model_name: str
    context_window: int
    max_output_tokens: int
    required_tokenizer_type: TokenizerType
    required_tokenizer_encoding: TokenizerEncoding
    thinking_config: ThinkingConfig
    thinking_enabled: bool = False


# Registry: provider -> model -> spec
MODEL_REGISTRY: dict[LLMProvider, dict[LLMModel, LLMModelSpec]] = {
    LLMProvider.CEREBRAS: {
        LLMModel.GPT_OSS_120B: LLMModelSpec(
            api_model_name="gpt-oss-120b",
            context_window=131_000,
            max_output_tokens=40_000,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(
                param_name="reasoning_effort",
                param_value="high",
            ),
            thinking_enabled=True,
        ),
        LLMModel.ZAI_GLM_4_7: LLMModelSpec(
            api_model_name="zai-glm-4.7",
            context_window=131_000,
            max_output_tokens=40_000,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(
                param_name="disable_reasoning",
                param_value=False,
            ),
            thinking_enabled=True,
        ),
    },
    LLMProvider.GROQ: {
        LLMModel.GPT_OSS_120B: LLMModelSpec(
            api_model_name="openai/gpt-oss-120b",
            context_window=131_000,
            max_output_tokens=40_000,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(
                param_name="reasoning_effort",
                param_value="high",
            ),
            thinking_enabled=True,
        ),
    },
    LLMProvider.ANTHROPIC: {
        LLMModel.CLAUDE_SONNET_4_6: LLMModelSpec(
            api_model_name="claude-sonnet-4-6",
            context_window=200_000,
            max_output_tokens=64_000,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(param_name="_noop", param_value=True),
        ),
        LLMModel.CLAUDE_SONNET_4_6_THINKING: LLMModelSpec(
            api_model_name="claude-sonnet-4-6",
            context_window=200_000,
            max_output_tokens=64_000,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(
                param_name="adaptive_thinking",
                param_value=True,
                effort="high",
            ),
            thinking_enabled=True,
        ),
        LLMModel.CLAUDE_SONNET_4_5: LLMModelSpec(
            api_model_name="claude-sonnet-4-5-20250929",
            context_window=200_000,
            max_output_tokens=16_384,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(param_name="_noop", param_value=True),
        ),
    },
    LLMProvider.TOGETHER: {
        # ── Kimi K2.5 ──────────────────────────────────────────────
        LLMModel.KIMI_K2_5: LLMModelSpec(
            api_model_name="moonshotai/Kimi-K2.5",
            context_window=256_000,
            max_output_tokens=64_000,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(param_name="reasoning", param_value=False),
        ),
        LLMModel.KIMI_K2_5_THINKING: LLMModelSpec(
            api_model_name="moonshotai/Kimi-K2.5",
            context_window=256_000,
            max_output_tokens=64_000,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(param_name="reasoning", param_value=True),
            thinking_enabled=True,
        ),
        # ── GLM-5 ─────────────────────────────────────────────────
        LLMModel.ZAI_GLM_5: LLMModelSpec(
            api_model_name="zai-org/GLM-5",
            context_window=200_000,
            max_output_tokens=64_000,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(param_name="reasoning", param_value=False),
        ),
        LLMModel.ZAI_GLM_5_THINKING: LLMModelSpec(
            api_model_name="zai-org/GLM-5",
            context_window=200_000,
            max_output_tokens=64_000,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(param_name="reasoning", param_value=True),
            thinking_enabled=True,
        ),
        # ── GLM-5 Dedicated (B200, Together) ─────────────────────
        LLMModel.ZAI_GLM_5_DEDICATED: LLMModelSpec(
            api_model_name="airweave/glm-5",
            context_window=200_000,
            max_output_tokens=64_000,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(param_name="reasoning", param_value=False),
        ),
        LLMModel.ZAI_GLM_5_DEDICATED_THINKING: LLMModelSpec(
            api_model_name="airweave/glm-5",
            context_window=200_000,
            max_output_tokens=64_000,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(param_name="reasoning", param_value=True),
            thinking_enabled=True,
        ),
        # ── Qwen 3.5 ──────────────────────────────────────────────
        LLMModel.QWEN_3_5: LLMModelSpec(
            api_model_name="Qwen/Qwen3.5-397B-A17B",
            context_window=256_000,
            max_output_tokens=81_920,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(param_name="reasoning", param_value=False),
        ),
        LLMModel.QWEN_3_5_THINKING: LLMModelSpec(
            api_model_name="Qwen/Qwen3.5-397B-A17B",
            context_window=256_000,
            max_output_tokens=81_920,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(param_name="reasoning", param_value=True),
            thinking_enabled=True,
        ),
        # ── Qwen 3.5 Dedicated (FP8, 4×H200) ───────────────────────
        LLMModel.QWEN_3_5_DEDICATED: LLMModelSpec(
            api_model_name="daan_0248/Qwen/Qwen3.5-397B-A17B-FP8-8e91e0d0",
            context_window=256_000,
            max_output_tokens=81_920,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(param_name="reasoning", param_value=False),
        ),
        LLMModel.QWEN_3_5_DEDICATED_THINKING: LLMModelSpec(
            api_model_name="daan_0248/Qwen/Qwen3.5-397B-A17B-FP8-8e91e0d0",
            context_window=256_000,
            max_output_tokens=81_920,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(param_name="reasoning", param_value=True),
            thinking_enabled=True,
        ),
        # ── MiniMax M2.5 ──────────────────────────────────────────
        LLMModel.MINIMAX_M2_5: LLMModelSpec(
            api_model_name="MiniMaxAI/MiniMax-M2.5",
            context_window=192_000,
            max_output_tokens=64_000,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(param_name="reasoning", param_value=False),
        ),
        LLMModel.MINIMAX_M2_5_THINKING: LLMModelSpec(
            api_model_name="MiniMaxAI/MiniMax-M2.5",
            context_window=192_000,
            max_output_tokens=64_000,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(param_name="reasoning", param_value=True),
            thinking_enabled=True,
        ),
    },
}


# Maps each provider to the settings attribute name for its API key.
PROVIDER_API_KEY_SETTINGS: dict[LLMProvider, str] = {
    LLMProvider.CEREBRAS: "CEREBRAS_API_KEY",
    LLMProvider.GROQ: "GROQ_API_KEY",
    LLMProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
    LLMProvider.TOGETHER: "TOGETHER_API_KEY",
}


def get_model_spec(provider: LLMProvider, model: LLMModel) -> LLMModelSpec:
    """Get model spec with validation."""
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
    """Get list of models available for a provider."""
    if provider not in MODEL_REGISTRY:
        raise ValueError(f"Unknown provider: {provider}")
    return list(MODEL_REGISTRY[provider].keys())
