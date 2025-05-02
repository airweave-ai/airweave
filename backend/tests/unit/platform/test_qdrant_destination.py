"""Unit tests for the Qdrant destination implementation."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.platform.configs.auth import QdrantAuthConfig
from airweave.platform.destinations.qdrant import QdrantDestination
from airweave.platform.entities._base import ChunkEntity


class MockChunkEntity(ChunkEntity):
    """Mock ChunkEntity for testing."""

    name: str = "Test Entity"
    description: str = "Test Description"


@pytest.fixture
def mock_entity():
    """Create a mock entity for testing."""
    entity = MockChunkEntity(
        entity_id="test_entity_id",
        db_entity_id=uuid.uuid4(),
        sync_id=uuid.uuid4(),
        vector=[0.1, 0.2, 0.3, 0.4],  # Simple test vector
    )
    return entity


@pytest.fixture
def mock_qdrant_client():
    """Create a mock Qdrant client."""
    mock_client = MagicMock()
    mock_client.get_collections.return_value = MagicMock(
        collections=[MagicMock(name="other_collection")]
    )
    return mock_client


class TestQdrantDestinationInit:
    """Tests for QdrantDestination initialization."""

    @pytest.mark.asyncio
    async def test_create(self):
        """Test creating a new QdrantDestination instance."""
        with (
            patch("airweave.platform.destinations.qdrant.QdrantClient") as mock_client_class,
            patch("airweave.platform.destinations.qdrant.settings") as mock_settings,
        ):
            # Mock the client response
            mock_client = mock_client_class.return_value
            mock_client.get_collections.return_value = MagicMock(collections=[])

            # Set the required environment variables via settings
            mock_settings.qdrant_url = "http://test-qdrant.com:6333"

            sync_id = uuid.uuid4()
            destination = await QdrantDestination.create(sync_id=sync_id, vector_size=384)

            # Validate initialization
            assert destination.sync_id == sync_id
            assert (
                destination.collection_name
                == f"Entities_{destination._sanitize_collection_name(sync_id)}"
            )
            assert destination.vector_size == 384
            assert destination.client is not None

            # Verify client was created
            mock_client_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_with_credentials(self):
        """Test creating a QdrantDestination with credentials."""
        with (
            patch("airweave.platform.destinations.qdrant.QdrantClient") as mock_client_class,
            patch(
                "airweave.platform.destinations.qdrant.QdrantDestination.get_credentials"
            ) as mock_get_credentials,
        ):
            # Setup mocks
            mock_client = mock_client_class.return_value
            mock_client.get_collections.return_value = MagicMock(collections=[])

            # Mock credentials
            mock_credentials = QdrantAuthConfig(
                url="https://test-qdrant.com", api_key="test-api-key"
            )
            mock_get_credentials.return_value = mock_credentials

            # Create instance
            sync_id = uuid.uuid4()
            destination = await QdrantDestination.create(sync_id=sync_id)

            # Validate initialization with credentials
            assert destination.url == "https://test-qdrant.com"
            assert destination.api_key == "test-api-key"

            # Verify client was created with credentials
            # Update the assert to match actual parameter order and structure
            mock_client_class.assert_called_once_with(
                location="https://test-qdrant.com",
                prefer_grpc=False,
                port=None,
                api_key="test-api-key",
            )


class TestQdrantDestinationConnection:
    """Tests for QdrantDestination connection methods."""

    @pytest.mark.asyncio
    async def test_connect_to_qdrant_with_settings(self):
        """Test connecting to Qdrant with settings."""
        with (
            patch("airweave.platform.destinations.qdrant.QdrantClient") as mock_client_class,
            patch("airweave.platform.destinations.qdrant.settings") as mock_settings,
        ):
            # Configure mocks with an actual string value instead of a MagicMock
            mock_settings.qdrant_url = "http://test-qdrant-settings.com:6333"
            mock_client = mock_client_class.return_value

            # Create and connect
            destination = QdrantDestination()
            await destination.connect_to_qdrant()

            # Verify client initialization with the correct location parameter and port=None
            mock_client_class.assert_called_once_with(
                location="http://test-qdrant-settings.com:6333", prefer_grpc=False, port=None
            )
            mock_client.get_collections.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_connection(self):
        """Test closing the connection."""
        # Setup destination with a client
        destination = QdrantDestination()
        destination.client = MagicMock()

        # Close connection
        await destination.close_connection()

        # Verify client was cleared
        assert destination.client is None


class TestQdrantDestinationCollections:
    """Tests for QdrantDestination collection management."""

    @pytest.mark.asyncio
    async def test_collection_exists_simple(self):
        """Test collection_exists with a simpler test."""
        # Setup
        with patch.object(QdrantDestination, "ensure_client_readiness", new_callable=AsyncMock):
            destination = QdrantDestination()
            destination.client = MagicMock()
            collection_name = "test_collection"

            # Create a collection response
            collection_mock = MagicMock()
            collection_mock.name = collection_name

            collections_response = MagicMock()
            collections_response.collections = [collection_mock]

            # Set up get_collections to return our response
            destination.client.get_collections.return_value = collections_response

            # Test the function
            result = await destination.collection_exists(collection_name)

            # Assert
            assert result is True
            destination.client.get_collections.assert_called_once()


class TestQdrantDestinationOperations:
    """Tests for QdrantDestination operations."""

    @pytest.mark.asyncio
    async def test_insert(self, mock_entity):
        """Test inserting a single entity."""
        # Create destination with a mock client
        destination = QdrantDestination()
        destination.client = MagicMock()
        destination.collection_name = "test_collection"

        # Insert entity
        await destination.insert(mock_entity)

        # Verify client call
        destination.client.upsert.assert_called_once()
        call_args = destination.client.upsert.call_args[1]
        assert call_args["collection_name"] == "test_collection"
        assert len(call_args["points"]) == 1
        point = call_args["points"][0]
        assert point.id == str(mock_entity.db_entity_id)
        assert point.vector == mock_entity.vector

    @pytest.mark.asyncio
    async def test_bulk_insert(self):
        """Test bulk inserting entities."""
        # Create destination with a mock client
        destination = QdrantDestination()
        destination.client = MagicMock()
        destination.collection_name = "test_collection"

        # Configure the mock to return a success response (no errors)
        mock_response = MagicMock()
        mock_response.errors = None  # No errors
        destination.client.upsert.return_value = mock_response

        # Create entities
        entities = [
            MockChunkEntity(
                entity_id=f"test_entity_id_{i}",
                db_entity_id=uuid.uuid4(),
                sync_id=uuid.uuid4(),
                vector=[0.1, 0.2, 0.3, 0.4],
            )
            for i in range(3)
        ]

        # Insert entities
        await destination.bulk_insert(entities)

        # Verify client call
        destination.client.upsert.assert_called_once()
        call_args = destination.client.upsert.call_args[1]
        assert call_args["collection_name"] == "test_collection"
        assert len(call_args["points"]) == 3

    @pytest.mark.asyncio
    async def test_search(self):
        """Test searching for entities."""
        # Create destination with a mock client
        destination = QdrantDestination()
        destination.client = MagicMock()
        destination.collection_name = "test_collection"
        destination.sync_id = uuid.uuid4()

        # Mock search results
        mock_results = [
            MagicMock(id="result1", score=0.95, payload={"field": "value1"}),
            MagicMock(id="result2", score=0.85, payload={"field": "value2"}),
        ]
        destination.client.search.return_value = mock_results

        # Perform search
        query_vector = [0.1, 0.2, 0.3, 0.4]
        results = await destination.search(query_vector)

        # Verify results
        assert len(results) == 2
        assert results[0]["id"] == "result1"
        assert results[0]["score"] == 0.95
        assert results[0]["payload"] == {"field": "value1"}


class TestQdrantDestinationUtilities:
    """Tests for QdrantDestination utility methods."""

    def test_sanitize_collection_name(self):
        """Test sanitizing collection name."""
        # Create a UUID with hyphens
        test_uuid = uuid.UUID("12345678-1234-5678-1234-567812345678")

        # Sanitize
        sanitized = QdrantDestination._sanitize_collection_name(test_uuid)

        # Verify hyphens are replaced with underscores
        assert sanitized == "12345678_1234_5678_1234_567812345678"
        assert "-" not in sanitized
