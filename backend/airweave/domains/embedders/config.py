"""Embedding config loader and validator.

Loads embedding configuration from the domain YAML file (embedding_config.yml),
which is the single source of truth for model and dimensions.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from airweave.core.config import Settings
from airweave.domains.embedders.dense.registry import (
    DENSE_MODEL_REGISTRY,
    get_model_spec,
    validate_vector_size,
)
from airweave.domains.embedders.exceptions import (
    EmbeddingConfigurationError,
)


@dataclass(frozen=True)
class EmbeddingConfig:
    """Resolved embedding configuration."""

    model: str
    dimensions: int
    provider: str


def load_embedding_config() -> EmbeddingConfig:
    """Load embedding config from domain YAML file.

    Returns:
        Resolved EmbeddingConfig with model, dimensions, and derived provider.

    Raises:
        EmbeddingConfigurationError: If YAML is missing or malformed.
    """
    path = Path(__file__).parent / "embedding_config.yml"

    if not path.exists():
        raise EmbeddingConfigurationError(
            f"Embedding config not found at {path}"
            ". Create embedding_config.yml with 'embedding.model' and 'embedding.dimensions'."
        )

    data = yaml.safe_load(path.read_text())

    embedding = data.get("embedding")

    if not embedding:
        raise EmbeddingConfigurationError("embedding_config.yml must have an 'embedding' section.")

    model = embedding.get("model")
    dimensions = embedding.get("dimensions")

    if not model:
        raise EmbeddingConfigurationError("embedding_config.yml: 'embedding.model' is required.")

    if not dimensions:
        raise EmbeddingConfigurationError(
            "embedding_config.yml: 'embedding.dimensions' is required."
        )

    provider = provider_for_model(model)

    return EmbeddingConfig(model=model, dimensions=int(dimensions), provider=provider)


def provider_for_model(model: str) -> str:
    """Find the provider that owns this model in the registry.

    Args:
        model: Model name (e.g. "text-embedding-3-small").

    Returns:
        Provider name (e.g. "openai").

    Raises:
        EmbeddingConfigurationError: If model is not in the registry.
    """
    for provider, models in DENSE_MODEL_REGISTRY.items():
        if model in models:
            return provider

    known = [m for models in DENSE_MODEL_REGISTRY.values() for m in models]
    raise EmbeddingConfigurationError(
        f"Unknown model '{model}' — not in registry. Known models: {known}"
    )


def validate_embedding_config(config: EmbeddingConfig, settings: Settings) -> None:
    """Validate that the config is usable.

    Checks:
    1. Model exists in registry (already validated by load_embedding_config)
    2. Dimensions are supported by the specific model
    3. Required API key is present for the provider

    Args:
        config: Resolved embedding config.
        settings: Application settings (for API key checks).

    Raises:
        EmbeddingConfigurationError: If validation fails.
    """
    try:
        spec = get_model_spec(config.provider, config.dimensions, model_name=config.model)
    except ValueError as e:
        raise EmbeddingConfigurationError(str(e)) from e

    try:
        validate_vector_size(spec, config.dimensions)
    except ValueError as e:
        raise EmbeddingConfigurationError(str(e)) from e

    validate_api_key(config.provider, settings)


def validate_api_key(provider: str, settings: Settings) -> None:
    """Ensure the required API key is present for the provider.

    Args:
        provider: Provider name.
        settings: Application settings.

    Raises:
        EmbeddingConfigurationError: If the API key is missing.
    """
    if provider == "local":
        return

    key_map = {
        "openai": settings.OPENAI_API_KEY,
        "mistral": settings.MISTRAL_API_KEY,
    }

    if not key_map.get(provider):
        raise EmbeddingConfigurationError(
            f"Provider '{provider}' requires an API key but none is configured. "
            "Set the appropriate API key environment variable."
        )
