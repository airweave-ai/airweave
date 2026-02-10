"""Refactored platform decorators with simplified capabilities."""

from typing import Callable, List, Optional, Type

from pydantic import BaseModel

from airweave.core.shared_models import RateLimitLevel
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
    supports_continuous: bool = False,
    federated_search: bool = False,
    supports_temporal_relevance: bool = True,
    rate_limit_level: Optional[RateLimitLevel] = None,
    cursor_class: Optional[Type[BaseModel]] = None,
    supports_access_control: bool = False,
    feature_flag: Optional[str] = None,
    internal: bool = False,
) -> Callable[[type], type]:
    """Enhanced source decorator with OAuth type tracking and typed cursor support.

    Args:
        name: Display name for the source
        short_name: Unique identifier for the source type
        auth_methods: List of supported authentication methods
        oauth_type: OAuth token type (for OAuth sources)
        requires_byoc: Whether this OAuth source requires user to bring their own client credentials
        auth_config_class: Pydantic model for auth configuration (for DIRECT auth only)
        config_class: Pydantic model for source configuration
        labels: Tags for categorization (e.g., "CRM", "Database")
        supports_continuous: Whether source supports cursor-based continuous syncing (default False)
        federated_search: Whether source uses federated search instead of syncing (default False)
        supports_temporal_relevance: Whether source entities have timestamps for (default True)
        cursor_class: Optional Pydantic model class for typed cursor (e.g., GmailCursor)
        rate_limit_level: Rate limiting level (RateLimitLevel.ORG, RateLimitLevel.CONNECTION,
            or None)
        supports_access_control: Whether this source provides entity-level access control
            metadata. When True, the source must:
            1. Set entity.access on all yielded entities
            2. Implement generate_access_control_memberships() method
            Default is False (entities visible to everyone).
        feature_flag: Optional feature flag (from FeatureFlag enum) required to access this source.
            When set, only organizations with this feature enabled can see/use the source.
        internal: Whether this is an internal/test source (default False). Internal
            sources are excluded from docs and only loaded when ENABLE_INTERNAL_SOURCES=true.

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

        # Source with access control (e.g., SharePoint)
        @source(
            name="SharePoint 2019 V2",
            short_name="sharepoint2019v2",
            auth_methods=[AuthenticationMethod.DIRECT],
            auth_config_class=SharePoint2019V2AuthConfig,
            config_class=SharePoint2019V2Config,
            labels=["Enterprise"],
            supports_access_control=True,  # Enables entity-level access control
        )
    """

    def decorator(cls: type) -> type:
        # Validate continuous sync configuration
        if supports_continuous and cursor_class is None:
            raise ValueError(
                f"Source '{short_name}' has supports_continuous=True but no cursor_class defined. "
                f"Continuous syncs require a typed cursor class (e.g., cursor_class=GmailCursor)"
            )

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
        cls._supports_continuous = supports_continuous
        cls._federated_search = federated_search
        cls._supports_temporal_relevance = supports_temporal_relevance
        cls._cursor_class = cursor_class
        cls._rate_limit_level = rate_limit_level
        cls._supports_access_control = supports_access_control
        cls._feature_flag = feature_flag
        cls._internal = internal

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
    auth_config_class: Optional[Type[BaseModel]] = None,
    config_class: Optional[Type[BaseModel]] = None,
    supports_upsert: bool = True,
    supports_delete: bool = True,
    supports_vector: bool = False,
    max_batch_size: int = 1000,
    requires_client_embedding: bool = True,
    supports_temporal_relevance: bool = True,
) -> Callable[[type], type]:
    """Decorator for destination connectors with separated auth and config.

    Args:
        name: Display name for the destination
        short_name: Unique identifier for the destination type
        auth_config_class: Pydantic model for authentication credentials (secrets)
        config_class: Pydantic model for destination configuration (parameters)
        supports_upsert: Whether destination supports upsert operations
        supports_delete: Whether destination supports delete operations
        supports_vector: Whether destination supports vector storage
        max_batch_size: Maximum batch size for write operations
        requires_client_embedding: Whether the destination requires client-side embedding
            generation (False for Vespa which embeds server-side)
        supports_temporal_relevance: Whether the destination supports temporal relevance
            ranking
    """

    def decorator(cls: type) -> type:
        cls._is_destination = True
        cls._name = name
        cls._short_name = short_name
        cls._auth_config_class = auth_config_class
        cls._config_class = config_class

        # Capability metadata
        cls._supports_upsert = supports_upsert
        cls._supports_delete = supports_delete
        cls._supports_vector = supports_vector
        cls._max_batch_size = max_batch_size
        cls._requires_client_embedding = requires_client_embedding
        cls._supports_temporal_relevance = supports_temporal_relevance

        return cls

    return decorator


# NOTE: Embedding model decorator removed - embeddings now handled by
# DenseEmbedder and SparseEmbedder in platform/embedders/


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


# NOTE: Transformer decorator removed - chunking now handled by
# CodeChunker and SemanticChunker in entity_pipeline.py
