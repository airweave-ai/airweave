"""Embedding stack validation at startup.

Validates that the embedding configuration in embedding_config.yml is valid
and that required API keys are present.
"""

from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.domains.embedders.config import load_embedding_config, validate_embedding_config
from airweave.domains.embedders.exceptions import EmbeddingConfigurationError


def validate_and_raise() -> None:
    """Validate embedding stack and raise if misconfigured.

    Loads config from domains/embedders/embedding_config.yml and validates
    that the model exists, dimensions are supported, and required API keys
    are available.

    Raises:
        EmbeddingConfigurationError: If configuration is invalid.
    """
    try:
        config = load_embedding_config()
        logger.info(
            f"[EmbeddingValidation] Config: model={config.model}, "
            f"dimensions={config.dimensions}, provider={config.provider}"
        )
        validate_embedding_config(config, settings)
        logger.info("[EmbeddingValidation] Embedding stack configuration is valid")
    except EmbeddingConfigurationError:
        raise
    except Exception as e:
        raise EmbeddingConfigurationError(
            f"Unexpected error validating embedding config: {e}"
        ) from e
