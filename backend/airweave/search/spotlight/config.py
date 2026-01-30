"""Configuration for spotlight search module."""

from enum import Enum


class DatabaseImpl(str, Enum):
    """Supported database implementations."""

    POSTGRESQL = "postgresql"


class SpotlightConfig:
    """Spotlight module configuration."""

    DATABASE_IMPL: DatabaseImpl = DatabaseImpl.POSTGRESQL


config = SpotlightConfig()
