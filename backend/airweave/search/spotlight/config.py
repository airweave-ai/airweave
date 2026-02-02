"""Configuration for spotlight search module."""

from enum import Enum


class DatabaseImpl(str, Enum):
    """Supported database implementations."""

    POSTGRESQL = "postgresql"


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    CEREBRAS = "cerebras"


class ModelName(str, Enum):
    """Supported model names (global across providers)."""

    GPT_OSS_120B = "gpt-oss-120b"


class SpotlightConfig:
    """Spotlight module configuration."""

    # Database
    DATABASE_IMPL: DatabaseImpl = DatabaseImpl.POSTGRESQL

    # LLM
    LLM_PROVIDER: LLMProvider = LLMProvider.CEREBRAS
    LLM_MODEL: ModelName = ModelName.GPT_OSS_120B


config = SpotlightConfig()
