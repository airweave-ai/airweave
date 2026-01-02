"""Handlers module for sync pipeline.

Contains handlers that execute resolved actions.

Handler Types:
- VectorDBHandler: For destinations requiring chunking/embedding (Qdrant, Pinecone)
- VespaHandler: For self-processing destinations (Vespa handles chunking/embedding)
- RawDataHandler: For raw data storage
- PostgresMetadataHandler: For metadata persistence (runs last)

The ActionDispatcher runs destination handlers concurrently, then PostgresMetadataHandler
sequentially to ensure consistency.
"""

from .base import ActionHandler
from .postgres import PostgresMetadataHandler
from .raw_data import RawDataHandler
from .vector_db import VectorDBHandler
from .vespa import VespaHandler

__all__ = [
    "ActionHandler",
    "PostgresMetadataHandler",
    "RawDataHandler",
    "VectorDBHandler",
    "VespaHandler",
]
