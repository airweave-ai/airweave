"""Configuration for agentic search module."""

from enum import Enum

# Shared constant: approximate characters per token for budget estimation.
CHARS_PER_TOKEN = 4


class DatabaseImpl(str, Enum):
    """Supported database implementations."""

    POSTGRESQL = "postgresql"


# --- LLM ---


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    CEREBRAS = "cerebras"
    GROQ = "groq"
    ANTHROPIC = "anthropic"
    TOGETHER = "together"


class LLMModel(str, Enum):
    """Supported LLM models (global across providers).

    A model can be hosted by multiple providers (e.g., GPT_OSS_120B on both
    Cerebras and Groq). The MODEL_REGISTRY in registry.py maps each
    (provider, model) pair to its provider-specific specification.
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
    MINIMAX_M2_5 = "minimax-m2.5"
    MINIMAX_M2_5_THINKING = "minimax-m2.5-thinking"


# --- Tokenizer ---


class TokenizerType(str, Enum):
    """Supported tokenizer implementations."""

    TIKTOKEN = "tiktoken"


class TokenizerEncoding(str, Enum):
    """Supported tokenizer encodings."""

    O200K_HARMONY = "o200k_harmony"


# --- Vector Database ---


class VectorDBProvider(str, Enum):
    """Supported vector database providers."""

    VESPA = "vespa"


# --- Config ---


class AgenticSearchConfig:
    """AgenticSearch module configuration."""

    # Database
    DATABASE_IMPL = DatabaseImpl.POSTGRESQL

    # LLM fallback chain — ordered list of (provider, model) pairs.
    # Tried in sequence: the first provider that is available (has an API key
    # configured) and responds successfully handles the request. Subsequent
    # providers are only tried when the previous one fails.
    #
    # To change the primary model, reorder this list or swap the model for a
    # provider. For example, to use GPT_OSS_120B on Cerebras instead of GLM:
    #   (LLMProvider.CEREBRAS, LLMModel.GPT_OSS_120B),
    LLM_FALLBACK_CHAIN: list[tuple[LLMProvider, LLMModel]] = [
        # (LLMProvider.ANTHROPIC, LLMModel.CLAUDE_SONNET_4_6),
        (LLMProvider.TOGETHER, LLMModel.ZAI_GLM_5),
        # (LLMProvider.TOGETHER, LLMModel.QWEN_3_5),
        # (LLMProvider.TOGETHER, LLMModel.MINIMAX_M2_5),
        # (LLMProvider.TOGETHER, LLMModel.KIMI_K2_5),
    ]

    # Tokenizer
    # Note: Must be compatible with the chosen LLM model (validated at startup)
    TOKENIZER_TYPE = TokenizerType.TIKTOKEN
    TOKENIZER_ENCODING = TokenizerEncoding.O200K_HARMONY

    # Vector database
    VECTOR_DB_PROVIDER = VectorDBProvider.VESPA

    # Agent loop
    MAX_ITERATIONS = 15  # tighter budget — agent pipelines multiple tool calls per iteration
    AGENT_LLM_MAX_RETRIES = 3
    AGENT_LLM_RETRY_DELAY = 2.0  # seconds, initial delay for exponential backoff
    STAGNATION_THRESHOLD = 4  # iterations without new marks before nudging
    READ_SURROUNDING_CHUNKS = 2  # ±N chunks around matched chunk in read tool


config = AgenticSearchConfig()
