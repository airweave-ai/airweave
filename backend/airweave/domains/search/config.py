"""Configuration for search module."""

from enum import Enum

from airweave.adapters.llm.registry import LLMModel, LLMProvider
from airweave.adapters.tokenizer.registry import TokenizerEncoding, TokenizerType

# Shared constant: approximate characters per token for budget estimation.
CHARS_PER_TOKEN = 4


class DatabaseImpl(str, Enum):
    """Supported database implementations."""

    POSTGRESQL = "postgresql"


# --- Vector Database ---


class VectorDBProvider(str, Enum):
    """Supported vector database providers."""

    VESPA = "vespa"


# --- Config ---


class SearchConfig:
    """Search module configuration."""

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


config = SearchConfig()
