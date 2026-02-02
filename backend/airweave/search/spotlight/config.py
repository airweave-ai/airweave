"""Configuration for spotlight search module."""

from enum import Enum

from airweave.search.spotlight.external.llm.registry import LLMProvider, ModelName


class DatabaseImpl(str, Enum):
    """Supported database implementations."""

    POSTGRESQL = "postgresql"


class TokenizerImpl(str, Enum):
    """Supported tokenizer implementations."""

    TIKTOKEN = "tiktoken"


class SpotlightConfig:
    """Spotlight module configuration.

    Pure settings - no logic. The services layer handles lookups and validation.
    """

    # Database
    DATABASE_IMPL: DatabaseImpl = DatabaseImpl.POSTGRESQL

    # LLM
    LLM_PROVIDER: LLMProvider = LLMProvider.CEREBRAS
    LLM_MODEL: ModelName = ModelName.GPT_OSS_120B

    # Tokenizer implementation (encoding is derived from model at composition time)
    TOKENIZER_IMPL: TokenizerImpl = TokenizerImpl.TIKTOKEN


config = SpotlightConfig()
