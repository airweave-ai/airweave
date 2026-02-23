"""Dense embedder model registry.

Maps provider names to their supported models and specifications.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DenseModelSpec:
    """Specification for a dense embedding model."""

    api_model_name: str
    max_dimensions: int
    default_dimensions: int
    supports_dimension_param: bool


DENSE_MODEL_REGISTRY: dict[str, dict[str, DenseModelSpec]] = {
    "openai": {
        "text-embedding-3-small": DenseModelSpec(
            api_model_name="text-embedding-3-small",
            max_dimensions=1536,
            default_dimensions=1536,
            supports_dimension_param=True,
        ),
        "text-embedding-3-large": DenseModelSpec(
            api_model_name="text-embedding-3-large",
            max_dimensions=3072,
            default_dimensions=3072,
            supports_dimension_param=True,
        ),
    },
    "mistral": {
        "mistral-embed": DenseModelSpec(
            api_model_name="mistral-embed",
            max_dimensions=1024,
            default_dimensions=1024,
            supports_dimension_param=False,
        ),
    },
    "local": {
        "sentence-transformers/all-MiniLM-L6-v2": DenseModelSpec(
            api_model_name="sentence-transformers/all-MiniLM-L6-v2",
            max_dimensions=384,
            default_dimensions=384,
            supports_dimension_param=False,
        ),
    },
}


def get_model_spec(
    provider: str, vector_size: int, model_name: str | None = None
) -> DenseModelSpec:
    """Get the model spec for a provider.

    When ``model_name`` is provided the lookup is exact — the named model must
    exist for the given provider.  When omitted, a heuristic selects the model:

    - OpenAI: text-embedding-3-small (<=1536) or text-embedding-3-large (>1536)
    - Other providers: the single available model

    Args:
        provider: Provider name (e.g. "openai", "mistral", "local").
        vector_size: Desired embedding dimensions.
        model_name: Explicit model name.  If given, must match a registry entry.

    Returns:
        DenseModelSpec for the selected model.

    Raises:
        ValueError: If provider is unknown or model_name is not in the registry.
    """
    provider_models = DENSE_MODEL_REGISTRY.get(provider)
    if not provider_models:
        raise ValueError(f"Unknown dense embedder provider: {provider}")

    # Exact lookup when model name is provided
    if model_name is not None:
        spec = provider_models.get(model_name)
        if spec is None:
            raise ValueError(
                f"Model '{model_name}' not found for provider '{provider}'. "
                f"Available: {list(provider_models.keys())}"
            )
        return spec

    # Heuristic fallback
    if provider == "openai":
        if vector_size <= 1536:
            return provider_models["text-embedding-3-small"]
        return provider_models["text-embedding-3-large"]

    return next(iter(provider_models.values()))


def get_model_name(provider: str) -> str:
    """Get the default model name for a provider.

    Args:
        provider: Provider name.

    Returns:
        Default model name string.
    """
    model_map = {
        "openai": "text-embedding-3-small",
        "mistral": "mistral-embed",
        "local": "sentence-transformers/all-MiniLM-L6-v2",
    }
    return model_map.get(provider, "sentence-transformers/all-MiniLM-L6-v2")


def validate_vector_size(spec: DenseModelSpec, vector_size: int) -> None:
    """Validate that the requested vector size is supported.

    Args:
        spec: Model specification.
        vector_size: Requested dimensions.

    Raises:
        ValueError: If vector_size exceeds model's max_dimensions.
    """
    if vector_size > spec.max_dimensions:
        raise ValueError(
            f"Model '{spec.api_model_name}' cannot produce {vector_size}-dim vectors "
            f"(max {spec.max_dimensions})."
        )
