"""Embedding configuration.

Simple utilities for embedding provider/model resolution.
Source of truth: settings.EMBEDDING_DIMENSIONS
"""

from typing import Optional

from airweave.core.config import settings

# =============================================================================
# Provider Detection
# =============================================================================


def get_default_provider() -> str:
    """Get default embedding provider based on available API keys.

    Priority: openai > mistral > local
    """
    if settings.OPENAI_API_KEY:
        return "openai"
    if settings.MISTRAL_API_KEY:
        return "mistral"
    return "local"


def get_provider_for_model(model_name: str) -> Optional[str]:
    """Infer provider from model name."""
    if not model_name:
        return None

    model_lower = model_name.lower()

    if "text-embedding" in model_lower:
        return "openai"
    if "mistral" in model_lower:
        return "mistral"
    if "minilm" in model_lower or "sentence-transformers" in model_lower:
        return "local"

    return None


# =============================================================================
# Dimension & Model Resolution
# =============================================================================


def get_default_dimensions() -> int:
    """Get configured embedding dimensions."""
    return settings.EMBEDDING_DIMENSIONS


def get_embedding_model(provider: Optional[str] = None) -> str:
    """Get the embedding model name for a provider.

    Args:
        provider: Provider name. If None, uses default provider.

    Returns:
        Model name string
    """
    provider = provider or get_default_provider()

    # Model selection based on provider
    # These are the standard models - dimensions come from settings.EMBEDDING_DIMENSIONS
    models = {
        "openai": "text-embedding-3-small",  # Supports Matryoshka (256-1536)
        "mistral": "mistral-embed",  # Supports variable dims
        "local": "sentence-transformers/all-MiniLM-L6-v2",
    }

    return models.get(provider, models["local"])


# =============================================================================
# Helpers
# =============================================================================


def is_mock_model(model_name: Optional[str]) -> bool:
    """Check if model name indicates a mock/test model."""
    return bool(model_name and "mock" in model_name.lower())
