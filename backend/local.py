import asyncio
import uuid
import os
from typing import List

from dotenv import load_dotenv
load_dotenv()

from airweave import schemas
from airweave.core.logging import ContextualLogger
from airweave.platform.destinations.weaviate import WeaviateDestination
from airweave.platform.embedders.openai import DenseEmbedder
from airweave.platform.sources._base import BaseSource
# from airweave.platform.sync.context import SyncContext

class MockSyncContext:
    def __init__(self, logger):
        self.logger = logger

async def main():
    """Entrypoint to test multiple connectors (Asana, Notion, Dropbox, etc.) end-to-end."""
    # Create a test user and a unique sync ID for this sync run
    organization_id = uuid.uuid4()
    user = schemas.User(
        id=uuid.uuid4(),
        email="test@test.com",
        full_name="Test User",
        primary_organization_id=organization_id,
    )
    sync_id = uuid.uuid4()
    collection_id = uuid.uuid4()

    # Initialize logger and sync context
    from airweave.core.logging import LoggerConfigurator
    logger = LoggerConfigurator.configure_logger(__name__)
    sync_context = MockSyncContext(logger)

    # Initialize an embedding model (OpenAI)
    # Ensure OPENAI_API_KEY is set in environment
    if not os.getenv("OPENAI_API_KEY"):
        print("WARNING: OPENAI_API_KEY not set. Embedding will fail.")
    
    embedding_model = DenseEmbedder(vector_size=3072)

    # Create a Weaviate destination for storing chunks
    print("=== Initializing Weaviate Destination ===")
    weaviate_dest = await WeaviateDestination.create(collection_id=collection_id)
    await weaviate_dest.setup_collection()
    print("=== Weaviate Destination Initialized ===")

    print("=== Verifying Weaviate Connection ===")
    if weaviate_dest.client.is_connected():
        print("Weaviate is ready and connected!")
    else:
        print("Failed to connect to Weaviate.")

    # -------------------------------------------------------------------------
    # Test Dummy Entity Insertion
    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------
    # Test Dummy Entity Insertion
    # -------------------------------------------------------------------------
    print("=== Testing Dummy Entity Insertion ===")
    from airweave.platform.entities._base import BaseEntity, AirweaveSystemMetadata
    from airweave.platform.entities._airweave_field import AirweaveField

    class DummyEntity(BaseEntity):
        entity_id: str = AirweaveField(..., description="ID", is_entity_id=True)
        name: str = AirweaveField(..., description="Name", is_name=True)
        url: str = AirweaveField(..., description="URL")

    dummy_entity = DummyEntity(
        entity_id="dummy_1",
        name="Dummy Entity",
        textual_representation="This is a test entity to verify Weaviate insertion.",
        source_id=uuid.uuid4(),
        url="http://example.com/dummy",
        breadcrumbs=[]
    )
    
    # Embed
    print("Generating embedding...")
    vectors = await embedding_model.embed_many([dummy_entity.textual_representation], sync_context)
    dummy_entity.airweave_system_metadata = AirweaveSystemMetadata(
        sync_id=sync_id,
        vectors=[vectors[0]]
    )
    
    # Insert
    print("Inserting into Weaviate...")
    await weaviate_dest.insert(dummy_entity)
    print("Successfully inserted dummy entity!")

    # -------------------------------------------------------------------------
    # Test Google Drive Source Connector (Placeholder)
    # -------------------------------------------------------------------------
    # To test with real data, uncomment and configure:
    # print("=== Testing Google Drive Connector ===")
    # from airweave.platform.sources.google_drive import GoogleDriveSource
    # google_drive_source = await GoogleDriveSource.create(user, sync_id)
    # await process_source_chunks(google_drive_source, weaviate_dest, embedding_model, sync_context)


if __name__ == "__main__":
    asyncio.run(main())
