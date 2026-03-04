"""Embedding stack validation at startup.

Validates that EMBEDDING_DIMENSIONS from .env is compatible with available providers.
"""

from typing import Dict, List, Tuple

from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.search.helpers import search_helpers


def get_provider_dimensions() -> Dict[str, List[int]]:
    """Load provider dimension capabilities from defaults.yml.

    Returns dict mapping provider name to list of supported dimensions.
    """
    defaults_data = search_helpers.load_defaults()
    provider_models = defaults_data.get("provider_models", {})

    provider_dims: Dict[str, List[int]] = {}

    for provider_name, models in provider_models.items():
        dims = set()

        # Check all embedding model variants
        for key, model_spec in models.items():
            if not isinstance(model_spec, dict):
                continue
            if not key.startswith("embedding"):
                continue

            # Get dimensions from model spec
            if "dimensions" in model_spec:
                dims.add(model_spec["dimensions"])

            # Also check supported_dimensions list (e.g., Mistral)
            if "supported_dimensions" in model_spec:
                dims.update(model_spec["supported_dimensions"])

        if dims:
            provider_dims[provider_name] = sorted(dims, reverse=True)

    return provider_dims


def get_available_providers() -> List[str]:
    """Get list of providers with configured API keys or local availability."""
    # TODO: USe enums/classes instead of strings for providers
    available = []

    if settings.OPENAI_API_KEY:
        available.append("openai")

    if settings.MISTRAL_API_KEY:
        available.append("mistral")

    # Local is available if TEXT2VEC_INFERENCE_URL is set
    # Note: LocalProvider for search is not yet implemented, but sync embeddings work
    if settings.TEXT2VEC_INFERENCE_URL:
        available.append("local")

    return available


def find_compatible_providers(dimensions: int) -> List[str]:
    """Find providers that support the given dimensions."""
    provider_dims = get_provider_dimensions()
    compatible = []
    for provider, supported_dims in provider_dims.items():
        if dimensions in supported_dims:
            compatible.append(provider)
    return compatible


def validate_embedding_stack() -> Tuple[bool, List[str]]:
    """Validate that the embedding stack is properly configured.

    Returns:
        Tuple of (is_valid, list of warning/error messages)
    """
    messages = []
    is_valid = True
    dim = settings.EMBEDDING_DIMENSIONS

    logger.info(f"[EmbeddingValidation] Configured EMBEDDING_DIMENSIONS={dim}")

    # Get available providers
    available = get_available_providers()
    if not available:
        messages.append(
            "WARNING: No embedding providers available. "
            "Set OPENAI_API_KEY, MISTRAL_API_KEY, or configure TEXT2VEC_INFERENCE_URL."
        )
        is_valid = False
    else:
        logger.info(f"[EmbeddingValidation] Available providers: {available}")

    # Find providers that support the configured dimensions
    provider_dims = get_provider_dimensions()
    compatible = find_compatible_providers(dim)

    if not compatible:
        available_dims_summary = (
            ", ".join(
                f"{name} ({', '.join(map(str, provider_dims.get(name, [])))})"
                for name in available
                if name in provider_dims
            )
            if available
            else "none configured"
        )

        messages.append(
            f"ERROR: No providers support EMBEDDING_DIMENSIONS={dim}. "
            f"Your configured providers support: {available_dims_summary}"
        )
        is_valid = False
    else:
        logger.info(f"[EmbeddingValidation] Providers supporting {dim} dimensions: {compatible}")

    # Check if any available provider is compatible
    available_and_compatible = [p for p in available if p in compatible]
    if available and compatible and not available_and_compatible:
        messages.append(
            f"ERROR: Available providers {available} don't support EMBEDDING_DIMENSIONS={dim}. "
            f"Compatible providers: {compatible}. "
            f"Either change EMBEDDING_DIMENSIONS or configure an API key for a compatible provider."
        )
        is_valid = False
    elif available_and_compatible:
        logger.info(f"[EmbeddingValidation] Will use provider(s): {available_and_compatible}")

    return is_valid, messages


class EmbeddingConfigurationError(Exception):
    """Raised when embedding stack is misconfigured."""

    pass


def validate_and_raise():
    """Validate embedding stack and raise if misconfigured.

    Raises:
        EmbeddingConfigurationError: If configuration is invalid
    """
    is_valid, messages = validate_embedding_stack()

    errors = [msg for msg in messages if msg.startswith("ERROR")]
    warnings = [msg for msg in messages if msg.startswith("WARNING")]
    reminders = [msg for msg in messages if msg.startswith("REMINDER")]

    # Log reminders
    for msg in reminders:
        logger.info(f"[EmbeddingValidation] {msg}")

    # Log warnings
    for msg in warnings:
        logger.warning(f"[EmbeddingValidation] {msg}")

    if is_valid:
        logger.info("[EmbeddingValidation] ✓ Embedding stack configuration is valid")
    else:
        # Log errors and raise
        for msg in errors:
            logger.error(f"[EmbeddingValidation] {msg}")

        error_summary = "; ".join(errors)
        raise EmbeddingConfigurationError(f"Embedding stack misconfigured: {error_summary}")
