"""Resource locator for platform resources."""

import importlib
from typing import Callable, Optional, Type

from airweave import schemas
from airweave.platform.auth.schemas import AuthType
from airweave.platform.configs._base import BaseConfig
from airweave.platform.destinations._base import BaseDestination
from airweave.platform.embedding_models._base import BaseEmbeddingModel
from airweave.platform.entities._base import BaseEntity
from airweave.platform.sources._base import BaseSource

PLATFORM_PATH = "airweave.platform"


class ResourceLocator:
    """Resource locator for platform resources.

    Gets the following:
    - embedding models
    - destinations
    - sources
    - configs
    - transformers
    """

    @staticmethod
    def get_embedding_model(model: schemas.EmbeddingModel) -> Type[BaseEmbeddingModel]:
        """Get the embedding model class.

        Args:
            model (schemas.EmbeddingModel): Embedding model schema

        Returns:
            Type[BaseEmbeddingModel]: Instantiated embedding model
        """
        module = importlib.import_module(f"{PLATFORM_PATH}.embedding_models.{model.short_name}")
        return getattr(module, model.class_name)

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
    def get_auth_config(
        auth_config_class: str, auth_type: Optional[str] = None
    ) -> Type[BaseConfig]:
        """Get the auth config class.

        Args:
            auth_config_class (str): Auth config class name
            auth_type (Optional[str]): Auth config class type

        Returns:
            Type[BaseConfig]: Auth config class
        """
        match auth_type:
            case AuthType.sigv4:
                module = importlib.import_module(f"{PLATFORM_PATH}.configs.sigv4")
                auth_config_class = getattr(module, auth_config_class)
                return auth_config_class
            case AuthType.config_class:
                module = importlib.import_module(f"{PLATFORM_PATH}.configs.auth")
                auth_config_class = getattr(module, auth_config_class)
                return auth_config_class
            case _:
                module = importlib.import_module(f"{PLATFORM_PATH}.configs.auth")
                auth_config_class = getattr(module, auth_config_class)
                return auth_config_class

    @staticmethod
    def get_transformer(transformer: schemas.Transformer) -> Callable:
        """Get the transformer function.

        Args:
            transformer (schemas.Transformer): Transformer schema

        Returns:
            Callable: Transformer function
        """
        module = importlib.import_module(transformer.module_name)
        return getattr(module, transformer.method_name)

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


resource_locator = ResourceLocator()
