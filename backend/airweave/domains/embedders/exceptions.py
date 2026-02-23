"""Embedder domain exceptions."""


class EmbedderProviderError(Exception):
    """Raised when an embedding provider call fails."""


class UnsupportedProviderError(ValueError):
    """Raised when the requested provider is unknown or unconfigured."""


class EmbeddingConfigurationError(Exception):
    """Raised when embedding configuration is invalid or incomplete."""
