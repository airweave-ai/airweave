"""Resource locator for platform resources."""

import importlib
from typing import Type

from airweave import schemas
from airweave.domains.auth_provider.types import AuthProviderMetadata
from airweave.platform.auth_providers._base import BaseAuthProvider
from airweave.platform.configs._base import BaseConfig
from airweave.platform.destinations._base import BaseDestination
from airweave.platform.entities._base import BaseEntity
from airweave.platform.sources._base import BaseSource

PLATFORM_PATH = "airweave.platform"


class ResourceLocator:
    """Resource locator for platform resources.

    Gets the following:
    - destinations
    - sources
    - auth providers
    - configs
    - entities
    """

    # NOTE: get_embedding_model removed - embeddings now handled by
    # DenseEmbedder and SparseEmbedder in platform/embedders/

    @staticmethod
    def get_source(source: schemas.Source) -> Type[BaseSource]:
        """Get the source class.

        Args:
            source (schemas.Source): Source schema

        Returns:
            Type[BaseSource]: Source class
        """
        module = importlib.import_module(f"{PLATFORM_PATH}.sources.{source.short_name}")
        return getattr(module, source.class_name)

    @staticmethod
    def get_destination(destination: schemas.Destination) -> Type[BaseDestination]:
        """Get the destination class.

        Args:
            destination (schemas.Destination): Destination schema

        Returns:
            Type[BaseDestination]: Destination class
        """
        module = importlib.import_module(f"{PLATFORM_PATH}.destinations.{destination.short_name}")
        return getattr(module, destination.class_name)

    @staticmethod
    def get_auth_provider(auth_provider: AuthProviderMetadata) -> Type[BaseAuthProvider]:
        """Get the auth provider class.

        Args:
            auth_provider (AuthProviderMetadata): Auth provider metadata

        Returns:
            Type[BaseAuthProvider]: Auth provider class
        """
        module = importlib.import_module(
            f"{PLATFORM_PATH}.auth_providers.{auth_provider.short_name}"
        )
        return getattr(module, auth_provider.class_name)

    @staticmethod
    def get_auth_config(auth_config_class: str) -> Type[BaseConfig]:
        """Get the auth config class.

        Args:
            auth_config_class (str): Auth config class name

        Returns:
            Type[BaseConfig]: Auth config class
        """
        module = importlib.import_module(f"{PLATFORM_PATH}.configs.auth")
        auth_config_class = getattr(module, auth_config_class)
        return auth_config_class

    @staticmethod
    def get_config(config_class: str) -> Type[BaseConfig]:
        """Get the config class.

        Args:
            config_class (str): Config class name

        Returns:
            Type[BaseConfig]: Config class
        """
        module = importlib.import_module(f"{PLATFORM_PATH}.configs.config")
        config_class = getattr(module, config_class)
        return config_class

    # NOTE: get_transformer removed - chunking now handled by
    # CodeChunker and SemanticChunker in entity_pipeline.py

    @staticmethod
    def get_entity_definition(entity_definition: schemas.EntityDefinition) -> Type[BaseEntity]:
        """Get the entity definition class.

        Args:
            entity_definition (schemas.EntityDefinition): Entity definition schema

        Returns:
            Type[BaseEntity]: Entity definition class
        """
        module = importlib.import_module(
            f"{PLATFORM_PATH}.entities.{entity_definition.module_name}"
        )
        return getattr(module, entity_definition.class_name)

    @staticmethod
    def get_available_auth_provider_classes() -> list[Type[BaseAuthProvider]]:
        """Get all available auth provider classes.

        Attempts to import each known auth provider and returns only those
        that are available. This allows graceful handling of optional providers.

        Returns:
            List of available auth provider classes
        """
        auth_provider_classes = []

        # List of known auth providers with their module and class names
        known_providers = [
            ("pipedream", "PipedreamAuthProvider"),
            ("composio", "ComposioAuthProvider"),
        ]

        for short_name, class_name in known_providers:
            module = importlib.import_module(f"{PLATFORM_PATH}.auth_providers.{short_name}")
            provider_class = getattr(module, class_name)
            auth_provider_classes.append(provider_class)

        return auth_provider_classes


resource_locator = ResourceLocator()
