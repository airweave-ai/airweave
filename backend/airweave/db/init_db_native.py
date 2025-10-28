"""Initialize the database with native connections."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.constants.reserved_ids import (
    NATIVE_NEO4J_UUID,
    NATIVE_QDRANT_UUID,
    RESERVED_TABLE_ENTITY_ID,
)
from airweave.core.shared_models import ConnectionStatus, IntegrationType
from airweave.models.connection import Connection


async def init_db_with_native_connections(db: AsyncSession) -> None:
    """Initialize the database with native connections.

    Creates the two built-in connections for:
    - qdrant_native (vector database destination)
    - neo4j_native (graph database destination)

    Note: Embedding models are no longer managed as connections.
    They are handled internally by DenseEmbedder and SparseEmbedder.

    These connections are system-level and don't belong to any organization.
    """
    # Check if connections already exist to avoid duplication on restarts
    native_connections = {
        "qdrant_native": {
            "id": NATIVE_QDRANT_UUID,
            "name": "Native Qdrant",
            "readable_id": "native-qdrant",
            "integration_type": IntegrationType.DESTINATION,
            "short_name": "qdrant_native",
            "status": ConnectionStatus.ACTIVE,
        },
        "neo4j_native": {
            "id": NATIVE_NEO4J_UUID,
            "name": "Native Neo4j",
            "readable_id": "native-neo4j",
            "integration_type": IntegrationType.DESTINATION,
            "short_name": "neo4j_native",
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
                readable_id=connection_data["readable_id"],
                integration_type=connection_data["integration_type"],
                short_name=connection_data["short_name"],
                status=connection_data["status"],
                # organization_id, created_by_email, and modified_by_email are
                # intentionally NULL for native connections
            )
            db.add(connection)

    await db.commit()


async def init_db_with_entity_definitions(db: AsyncSession) -> None:
    """Initialize the database with entity definitions.

    Creates the reserved ID for the PolymorphicEntity class.
    """
    from airweave.models.entity_definition import EntityDefinition, EntityType

    # Check if the polymorphic entity definition already exists
    result = await db.execute(
        text("SELECT id FROM entity_definition WHERE id = :id"),
        {"id": str(RESERVED_TABLE_ENTITY_ID)},
    )
    existing_entity = result.scalar_one_or_none()

    if not existing_entity:
        # Create the polymorphic table entity definition
        entity_def = EntityDefinition(
            id=RESERVED_TABLE_ENTITY_ID,
            name="Polymorphic Table Entity",
            description="Base entity type for polymorphic table entities",
            type=EntityType.JSON,
            entity_schema={},  # Empty schema for polymorphic entities
            module_name="airweave.platform.entities.polymorphic",
            class_name="PolymorphicEntity",
            # organization_id is NULL for system-level entity definitions
        )
        db.add(entity_def)
        await db.commit()
