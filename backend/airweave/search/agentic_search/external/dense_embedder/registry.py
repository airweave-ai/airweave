"""Dense embedder model registry.

Centralizes knowledge about available embedding models and their capabilities.
"""

from dataclasses import dataclass

from airweave.search.agentic_search.config import DenseEmbedderModel, DenseEmbedderProvider


@dataclass(frozen=True)
class DenseEmbedderModelSpec:
    """Specification for a dense embedding model.

    Attributes:
        api_model_name: The model name used in API calls.
        max_dimensions: Maximum embedding dimensions supported.
        default_dimensions: Default embedding dimensions if not specified.
        supports_dimension_param: Whether the model supports custom dimensions (Matryoshka).
    """

    api_model_name: str
    max_dimensions: int
    default_dimensions: int
    supports_dimension_param: bool


# Registry of all models by provider
DENSE_EMBEDDER_REGISTRY: dict[
    DenseEmbedderProvider, dict[DenseEmbedderModel, DenseEmbedderModelSpec]
] = {
    DenseEmbedderProvider.OPENAI: {
        DenseEmbedderModel.TEXT_EMBEDDING_3_SMALL: DenseEmbedderModelSpec(
            api_model_name="text-embedding-3-small",
            max_dimensions=1536,
            default_dimensions=1536,
            supports_dimension_param=True,
        ),
        DenseEmbedderModel.TEXT_EMBEDDING_3_LARGE: DenseEmbedderModelSpec(
            api_model_name="text-embedding-3-large",
            max_dimensions=3072,
            default_dimensions=3072,
            supports_dimension_param=True,
        ),
    },
}


def get_model_spec(
    provider: DenseEmbedderProvider,
    model: DenseEmbedderModel,
) -> DenseEmbedderModelSpec:
    """Get model spec with validation.

    Args:
        provider: The embedder provider.
        model: The model name.

    Returns:
        DenseEmbedderModelSpec for the provider/model combination.

    Raises:
        ValueError: If provider is not in the registry.
        ValueError: If model is not supported by the provider.
    """
    if provider not in DENSE_EMBEDDER_REGISTRY:
        raise ValueError(f"Unknown dense embedder provider: {provider.value}")

    provider_models = DENSE_EMBEDDER_REGISTRY[provider]
    if model not in provider_models:
        available = [m.value for m in provider_models.keys()]
        raise ValueError(
            f"Model '{model.value}' not supported by {provider.value}. Available: {available}"
        )

    return provider_models[model]


def validate_vector_size(model_spec: DenseEmbedderModelSpec, vector_size: int) -> None:
    """Validate that the model can produce the requested vector size.

    Args:
        model_spec: The model specification.
        vector_size: The required embedding dimension.

    Raises:
        ValueError: If vector_size exceeds the model's maximum.
    """
    if vector_size > model_spec.max_dimensions:
        raise ValueError(
            f"Model '{model_spec.api_model_name}' cannot produce {vector_size} dimensions. "
            f"Maximum supported: {model_spec.max_dimensions}"
        )
