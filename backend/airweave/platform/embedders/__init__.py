"""Embedders for dense and sparse vector computation.

Dense embedders generate fixed-size vectors for semantic similarity.
Sparse embedders generate variable-length token vectors for keyword matching.

Use get_dense_embedder() to get the appropriate embedder based on provider/model.
"""

from airweave.core.config import settings

from ._base import BaseEmbedder
from .config import (
    get_default_provider,
    get_embedding_model,
    get_provider_for_model,
)
from .fastembed import SparseEmbedder
from .local import LocalDenseEmbedder
from .mistral import MistralDenseEmbedder
from .openai import OpenAIDenseEmbedder


def _resolve_provider(model_name: str | None, provider: str | None) -> str:
    """Resolve embedding provider from model name or default."""
    if provider is not None:
        return provider
    if model_name:
        inferred = get_provider_for_model(model_name)
        if inferred:
            return inferred
    return get_default_provider()


def get_dense_embedder(
    vector_size: int | None = None,
    model_name: str | None = None,
    provider: str | None = None,
) -> BaseEmbedder:
    """Get the appropriate dense embedder for the given configuration.

    Args:
        vector_size: Target embedding dimensions (default: settings.EMBEDDING_DIMENSIONS)
        model_name: Explicit model name (optional)
        provider: Explicit provider (optional, inferred from API keys)

    Returns:
        Configured dense embedder instance

    Example:
        # Let the system decide based on settings
        embedder = get_dense_embedder()

        # Explicit dimensions
        embedder = get_dense_embedder(vector_size=1024)

        # Explicit provider
        embedder = get_dense_embedder(provider="mistral")
    """
    vector_size = vector_size or settings.EMBEDDING_DIMENSIONS
    provider = _resolve_provider(model_name, provider)
    model_name = model_name or get_embedding_model(provider)

    if provider == "mistral":
        return MistralDenseEmbedder(model_name=model_name, vector_size=vector_size)
    if provider == "openai":
        return OpenAIDenseEmbedder(vector_size=vector_size)
    if provider == "local":
        return LocalDenseEmbedder(vector_size=vector_size, model_name=model_name)

    raise ValueError(f"Unknown embedding provider: {provider}")


# Legacy alias for backward compatibility
DenseEmbedder = OpenAIDenseEmbedder

__all__ = [
    # Base
    "BaseEmbedder",
    # Dense embedders
    "OpenAIDenseEmbedder",
    "MistralDenseEmbedder",
    "LocalDenseEmbedder",
    "DenseEmbedder",  # Legacy alias
    # Sparse embedders
    "SparseEmbedder",
    # Factory
    "get_dense_embedder",
    # Config re-exports
    "get_default_provider",
    "get_provider_for_model",
    "get_embedding_model",
]
