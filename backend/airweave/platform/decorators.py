"""Refactored platform decorators with simplified capabilities."""

from functools import wraps
from typing import Callable, List, Optional, Type, TypeVar

from pydantic import BaseModel

from airweave.platform.entities._base import ChunkEntity
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


def source(
    name: str,
    short_name: str,
    auth_methods: List[AuthenticationMethod],
    oauth_type: Optional[OAuthType] = None,
    requires_byoc: bool = False,
    auth_config_class: Optional[Type[BaseModel]] = None,
    config_class: Optional[Type[BaseModel]] = None,
    labels: Optional[List[str]] = None,
) -> Callable[[type], type]:
    """Enhanced source decorator with OAuth type tracking.

    Args:
        name: Display name for the source
        short_name: Unique identifier for the source type
        auth_methods: List of supported authentication methods
        oauth_type: OAuth token type (for OAuth sources)
        requires_byoc: Whether this OAuth source requires user to bring their own client credentials
        auth_config_class: Pydantic model for auth configuration (for DIRECT auth only)
        config_class: Pydantic model for source configuration
        labels: Tags for categorization (e.g., "CRM", "Database")

    Example:
        # OAuth source (no auth config)
        @source(
            name="Gmail",
            short_name="gmail",
            auth_methods=[AuthenticationMethod.OAUTH_BROWSER, AuthenticationMethod.OAUTH_TOKEN],
            oauth_type=OAuthType.WITH_REFRESH,
            auth_config_class=None,  # OAuth sources don't need this
            config_class=GmailConfig,
            labels=["Email"],
        )

        # Direct auth source (keeps auth config)
        @source(
            name="GitHub",
            short_name="github",
            auth_methods=[AuthenticationMethod.DIRECT],
            oauth_type=None,
            auth_config_class=GitHubAuthConfig,  # Direct auth needs this
            config_class=GitHubConfig,
            labels=["Developer Tools"],
        )
    """

    def decorator(cls: type) -> type:
        # Set metadata as class attributes
        cls._is_source = True
        cls._name = name
        cls._short_name = short_name
        cls._auth_methods = auth_methods
        cls._oauth_type = oauth_type
        cls._requires_byoc = requires_byoc
        cls._auth_config_class = auth_config_class
        cls._config_class = config_class
        cls._labels = labels or []

        # Add validation method if not present
        if not hasattr(cls, "validate"):

            async def validate(self) -> bool:
                """Default validation that always passes."""
                return True

            cls.validate = validate

        return cls

    return decorator


def destination(
    name: str,
    short_name: str,
    config_class: Optional[Type[BaseModel]] = None,
    supports_upsert: bool = True,
    supports_delete: bool = True,
    supports_vector: bool = False,
    max_batch_size: int = 1000,
) -> Callable[[type], type]:
    """Decorator for destination connectors.

    Args:
        name: Display name for the destination
        short_name: Unique identifier for the destination type
        config_class: Pydantic model for destination configuration
        labels: Tags for categorization
        supports_upsert: Whether destination supports upsert operations
        supports_delete: Whether destination supports delete operations
        supports_vector: Whether destination supports vector storage
        max_batch_size: Maximum batch size for write operations
    """

    def decorator(cls: type) -> type:
        cls._is_destination = True
        cls._name = name
        cls._short_name = short_name
        cls._config_class = config_class

        # Capability metadata
        cls._supports_upsert = supports_upsert
        cls._supports_delete = supports_delete
        cls._supports_vector = supports_vector
        cls._max_batch_size = max_batch_size

        return cls

    return decorator


def embedding_model(
    name: str,
    short_name: str,
    provider: str,
    auth_config_class: Optional[str] = None,
    model_name: Optional[str] = None,
    model_version: Optional[str] = None,
    dimensions: int = 1536,
    max_tokens: int = 8192,
    supports_batch: bool = True,
    batch_size: int = 100,
) -> Callable[[type], type]:
    """Decorator for embedding model implementations.

    Args:
        name: Display name for the embedding model
        short_name: Unique identifier for the model
        provider: Provider name (e.g., "openai", "cohere", "huggingface")
        auth_config_class: Authentication config class (optional, for API key auth)
        model_name: Actual model name (defaults to name)
        model_version: Model version
        dimensions: Vector dimensions output by the model
        max_tokens: Maximum input tokens
        supports_batch: Whether model supports batch processing
        batch_size: Maximum batch size for embedding
    """

    def decorator(cls: type) -> type:
        cls._is_embedding_model = True
        cls._name = name
        cls._short_name = short_name
        cls._auth_config_class = auth_config_class
        cls._model_name = model_name if model_name else cls._name
        cls._model_version = model_version if model_version else "1.0"
        cls._provider = provider
        cls._model_name = model_name or name
        cls._model_version = model_version or "1.0"

        # Capability metadata
        cls._dimensions = dimensions
        cls._max_tokens = max_tokens
        cls._supports_batch = supports_batch
        cls._batch_size = batch_size

        return cls

    return decorator


def auth_provider(
    name: str,
    short_name: str,
    auth_config_class: str,
    config_class: str,
) -> Callable[[type], type]:
    """Class decorator to mark a class as representing an Airweave auth provider.

    Args:
    ----
        name (str): The name of the auth provider.
        short_name (str): The short name of the auth provider.
        auth_config_class (str): The authentication config class of the auth provider.
        config_class (str): The configuration class for the auth provider.

    Returns:
    -------
        Callable[[type], type]: The decorated class.

    """

    def decorator(cls: type) -> type:
        cls._is_auth_provider = True
        cls._name = name
        cls._short_name = short_name
        cls._auth_config_class = auth_config_class
        cls._config_class = config_class
        return cls

    return decorator


T = TypeVar("T", bound=ChunkEntity)
U = TypeVar("U", bound=ChunkEntity)


def transformer(
    name: str,
    description: Optional[str] = None,
    input_type: Optional[Type[ChunkEntity]] = None,
    output_type: Optional[Type[ChunkEntity]] = None,
    config_schema: Optional[dict] = None,
    supports_batch: bool = True,
    preserves_metadata: bool = True,
) -> Callable[[Callable], Callable]:
    """Method decorator to mark a function as an Airweave transformer.

    Transformers are functions that process entities during the sync pipeline,
    modifying or enriching them before they reach the destination.

    Args:
        name: Name of the transformer
        description: Human-readable description
        input_type: Expected input entity type
        output_type: Output entity type (if different from input)
        config_schema: JSON schema for transformer configuration
        supports_batch: Whether transformer can process multiple entities at once
        preserves_metadata: Whether transformer preserves entity metadata

    Example:
        @transformer(
            name="Extract Keywords",
            description="Extracts keywords from text content",
            input_type=DocumentEntity,
            output_type=DocumentEntity,
            supports_batch=True,
        )
        async def extract_keywords(
            entities: List[DocumentEntity], config: dict
        ) -> List[DocumentEntity]:
            # Process entities
            return entities
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        # Add transformer metadata
        wrapper._is_transformer = True
        wrapper._name = name
        wrapper._description = description or func.__doc__
        wrapper._input_type = input_type
        wrapper._output_type = output_type or input_type
        wrapper._config_schema = config_schema or {}
        wrapper._supports_batch = supports_batch
        wrapper._preserves_metadata = preserves_metadata
        wrapper._method_name = func.__name__

        return wrapper

    return decorator
