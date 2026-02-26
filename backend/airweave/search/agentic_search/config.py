"""Configuration for agentic search module."""

from enum import Enum


class DatabaseImpl(str, Enum):
    """Supported database implementations."""

    POSTGRESQL = "postgresql"


# --- LLM ---


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    CEREBRAS = "cerebras"
    GROQ = "groq"
    ANTHROPIC = "anthropic"


class LLMModel(str, Enum):
    """Supported LLM models (global across providers).

    A model can be hosted by multiple providers (e.g., GPT_OSS_120B on both
    Cerebras and Groq). The MODEL_REGISTRY in registry.py maps each
    (provider, model) pair to its provider-specific specification.
    """

    GPT_OSS_120B = "gpt-oss-120b"
    ZAI_GLM_4_7 = "zai-glm-4.7"
    CLAUDE_SONNET_4_5 = "claude-sonnet-4.5"


# --- Tokenizer ---


class TokenizerType(str, Enum):
    """Supported tokenizer implementations."""

    TIKTOKEN = "tiktoken"


class TokenizerEncoding(str, Enum):
    """Supported tokenizer encodings."""

    O200K_HARMONY = "o200k_harmony"


# --- Dense Embedder ---


class DenseEmbedderProvider(str, Enum):
    """Supported dense embedder providers."""

    OPENAI = "openai"


class DenseEmbedderModel(str, Enum):
    """Supported dense embedding models."""

    TEXT_EMBEDDING_3_SMALL = "text-embedding-3-small"
    TEXT_EMBEDDING_3_LARGE = "text-embedding-3-large"


# --- Sparse Embedder ---


class SparseEmbedderProvider(str, Enum):
    """Supported sparse embedder providers."""

    FASTEMBED = "fastembed"


class SparseEmbedderModel(str, Enum):
    """Supported sparse embedding models."""

    BM25 = "Qdrant/bm25"


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
        (LLMProvider.CEREBRAS, LLMModel.ZAI_GLM_4_7),
        (LLMProvider.GROQ, LLMModel.GPT_OSS_120B),
        (LLMProvider.ANTHROPIC, LLMModel.CLAUDE_SONNET_4_5),
    ]

    # Tokenizer
    # Note: Must be compatible with the chosen LLM model (validated at startup)
    TOKENIZER_TYPE = TokenizerType.TIKTOKEN
    TOKENIZER_ENCODING = TokenizerEncoding.O200K_HARMONY

    # Dense embedder
    # Must match the model used by the sync pipeline's embedder.
    # The sync pipeline uses text-embedding-3-small for dims <= 1536
    # and text-embedding-3-large for dims > 1536. Using the wrong model
    # here produces query embeddings in a different vector space than
    # the stored document embeddings, making semantic search useless.
    DENSE_EMBEDDER_PROVIDER = DenseEmbedderProvider.OPENAI
    DENSE_EMBEDDER_MODEL = DenseEmbedderModel.TEXT_EMBEDDING_3_LARGE

    # Sparse embedder
    SPARSE_EMBEDDER_PROVIDER = SparseEmbedderProvider.FASTEMBED
    SPARSE_EMBEDDER_MODEL = SparseEmbedderModel.BM25

    # Vector database
    VECTOR_DB_PROVIDER = VectorDBProvider.VESPA


config = AgenticSearchConfig()
