"""Sparse embedder model registry.

Centralizes knowledge about available sparse embedding models and their capabilities.
"""

from dataclasses import dataclass

from airweave.search.agentic_search.config import SparseEmbedderModel, SparseEmbedderProvider


@dataclass(frozen=True)
class SparseEmbedderModelSpec:
    """Specification for a sparse embedding model.

    Attributes:
        model_name: The model name used to load the model (e.g., "Qdrant/bm25").
        description: Brief description of the model characteristics.
    """

    model_name: str


# Registry of all models by provider
SPARSE_EMBEDDER_REGISTRY: dict[
    SparseEmbedderProvider, dict[SparseEmbedderModel, SparseEmbedderModelSpec]
] = {
    SparseEmbedderProvider.FASTEMBED: {
        SparseEmbedderModel.BM25: SparseEmbedderModelSpec(
            model_name="Qdrant/bm25",
        ),
    },
}


def get_model_spec(
    provider: SparseEmbedderProvider,
    model: SparseEmbedderModel,
) -> SparseEmbedderModelSpec:
    """Get model spec with validation.

    Args:
        provider: The embedder provider.
        model: The model name.

    Returns:
        SparseEmbedderModelSpec for the provider/model combination.

    Raises:
        ValueError: If provider is not in the registry.
        ValueError: If model is not supported by the provider.
    """
    if provider not in SPARSE_EMBEDDER_REGISTRY:
        raise ValueError(f"Unknown sparse embedder provider: {provider.value}")

    provider_models = SPARSE_EMBEDDER_REGISTRY[provider]
    if model not in provider_models:
        available = [m.value for m in provider_models.keys()]
        raise ValueError(
            f"Model '{model.value}' not supported by {provider.value}. Available: {available}"
        )

    return provider_models[model]
