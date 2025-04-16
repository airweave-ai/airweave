"""Initialize the database with native connections."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.constants.native_connections import (
    NATIVE_NEO4J_UUID,
    NATIVE_QDRANT_UUID,
    NATIVE_TEXT2VEC_UUID,
)
from airweave.core.shared_models import ConnectionStatus, IntegrationType
from airweave.models.connection import Connection


async def init_db_with_native_connections(db: AsyncSession) -> None:
    """Initialize the database with native connections.

    Creates the three built-in connections for:
    - qdrant_native (vector database destination)
    - neo4j_native (graph database destination)
    - local_text2vec (embedding model)

    These connections are system-level and don't belong to any organization.
    """
    # Check if connections already exist to avoid duplication on restarts
    native_connections = {
        "qdrant_native": {
            "id": NATIVE_QDRANT_UUID,
            "name": "Native Qdrant",
            "integration_type": IntegrationType.DESTINATION,
            "short_name": "qdrant_native",
            "status": ConnectionStatus.ACTIVE,
        },
        "neo4j_native": {
            "id": NATIVE_NEO4J_UUID,
            "name": "Native Neo4j",
            "integration_type": IntegrationType.DESTINATION,
            "short_name": "neo4j_native",
            "status": ConnectionStatus.ACTIVE,
        },
        "local_text2vec": {
            "id": NATIVE_TEXT2VEC_UUID,
            "name": "Local Text2Vec",
            "integration_type": IntegrationType.EMBEDDING_MODEL,
            "short_name": "local_text2vec",
            "status": ConnectionStatus.ACTIVE,
        },
    }

    # Create connections if they don't exist
    for short_name, connection_data in native_connections.items():
        # Check if connection already exists
        result = await db.execute(
            text("SELECT id FROM connection WHERE short_name = :short_name"),
            {"short_name": short_name},
        )
        existing_connection = result.scalar_one_or_none()

        if not existing_connection:
            connection = Connection(
                id=connection_data["id"],
                name=connection_data["name"],
                integration_type=connection_data["integration_type"],
                short_name=connection_data["short_name"],
                status=connection_data["status"],
                # organization_id, created_by_email, and modified_by_email are
                # intentionally NULL for native connections
            )
            db.add(connection)

    await db.commit()
