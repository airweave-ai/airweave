"""Model registry for LLM adapters.

Single source of truth for all provider-model combinations and their specifications.
The fallback chain (which combinations to use and in what order) is configured in
SearchConfig, not here. This module is purely a catalog.

Thinking/reasoning is controlled per-call via the `thinking` parameter on chat(),
not per-model. The ThinkingConfig tells providers *how* to toggle thinking (which
API parameter to use), but not *whether* to — that comes from the request.
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

    Thinking is toggled per-call, so there are no separate -thinking variants.
    """

    GPT_OSS_120B = "gpt-oss-120b"
    ZAI_GLM_4_7 = "zai-glm-4.7"
    ZAI_GLM_5 = "zai-glm-5"
    CLAUDE_SONNET_4_5 = "claude-sonnet-4.5"
    CLAUDE_SONNET_4_6 = "claude-sonnet-4.6"
    KIMI_K2_5 = "kimi-k2.5"
    QWEN_3_5 = "qwen-3.5"
    QWEN_3_5_DEDICATED = "qwen-3.5-dedicated"
    ZAI_GLM_5_DEDICATED = "zai-glm-5-dedicated"
    MINIMAX_M2_5 = "minimax-m2.5"


@dataclass(frozen=True)
class ThinkingConfig:
    """Model-specific thinking/reasoning API configuration.

    Tells providers which API parameter to use when toggling thinking on/off:
    - Together (GLM/Qwen/Kimi/MiniMax): reasoning={"enabled": True/False}
    - Cerebras GPT-OSS: reasoning_effort="high"/"low"
    - Cerebras GLM: disable_reasoning=True/False
    - Anthropic 4.6: adaptive thinking with effort="high"
    - Anthropic 4.5: no thinking support (param_name="_noop")

    The actual on/off decision comes from the `thinking` parameter on chat(),
    not from param_value here. param_value is unused in the per-call model.
    """

    param_name: str
    param_value: Union[str, bool, int]  # kept for backward compat, unused in per-call model
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
        ),
    },
    LLMProvider.ANTHROPIC: {
        LLMModel.CLAUDE_SONNET_4_6: LLMModelSpec(
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
        # ── GLM-5 ─────────────────────────────────────────────────
        LLMModel.ZAI_GLM_5: LLMModelSpec(
            api_model_name="zai-org/GLM-5",
            context_window=200_000,
            max_output_tokens=64_000,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(param_name="reasoning", param_value=False),
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
        # ── Qwen 3.5 ──────────────────────────────────────────────
        LLMModel.QWEN_3_5: LLMModelSpec(
            api_model_name="Qwen/Qwen3.5-397B-A17B",
            context_window=256_000,
            max_output_tokens=81_920,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(param_name="reasoning", param_value=False),
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
        # ── MiniMax M2.5 ──────────────────────────────────────────
        LLMModel.MINIMAX_M2_5: LLMModelSpec(
            api_model_name="MiniMaxAI/MiniMax-M2.5",
            context_window=192_000,
            max_output_tokens=64_000,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(param_name="reasoning", param_value=False),
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
