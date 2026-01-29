"""Configuration module for Airweave backend.

Provides centralized configuration management with type-safe enums.

Usage:
    from airweave.core.config import settings, StorageBackendType, Environment

    # Access settings
    if settings.STORAGE_BACKEND == StorageBackendType.AWS:
        ...

    # Use enums for type safety
    if settings.ENVIRONMENT == Environment.PRD:
        ...
"""

from airweave.core.config.enums import Environment, StorageBackendType
from airweave.core.config.settings import Settings

__all__ = [
    "Settings",
    "StorageBackendType",
    "Environment",
    "settings",
]

# Singleton settings instance
settings = Settings()
