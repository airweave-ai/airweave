"""CRUD operations for the application."""

from .crud_api_key import api_key
from .crud_auth_provider import auth_provider
from .crud_collection import collection
from .crud_connection import connection
from .crud_dag import sync_dag
from .crud_destination import destination
from .crud_embedding_model import embedding_model
from .crud_entity import entity
from .crud_entity_definition import entity_definition
from .crud_integration_credential import integration_credential
from .crud_organization import organization
from .crud_source import source
from .crud_source_connection import source_connection
from .crud_sync import sync
from .crud_sync_cursor import sync_cursor
from .crud_sync_job import sync_job
from .crud_transformer import transformer
from .crud_user import user
from .crud_white_label import white_label

__all__ = [
    # Existing CRUD instances
    "api_key",
    "auth_provider",
    "collection",
    "connection",
    "destination",
    "embedding_model",
    "entity",
    "entity_definition",
    "integration_credential",
    "organization",
    "source",
    "source_connection",
    "sync",
    "sync_cursor",
    "sync_dag",
    "sync_job",
    "transformer",
    "user",
    "white_label",
]
