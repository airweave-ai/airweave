"""Tests for Neo4j graph database source connector.

Tests Neo4j connector functionality with mocked driver responses
matching Neo4j's actual async driver API format.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict, List

from airweave.platform.sources.neo4j import Neo4jSource
from airweave.platform.configs.auth import Neo4jAuthConfig


# Mock Neo4j node class
class MockNode:
    """Mock Neo4j node object."""

    def __init__(self, element_id: str, node_id: int, labels: List[str], properties: Dict[str, Any]):
        self.element_id = element_id
        self.id = node_id
        self._labels = labels
        self._properties = properties

    def items(self):
        """Return node properties as items."""
        return self._properties.items()

    def __getitem__(self, key):
        """Get property value."""
        return self._properties[key]


# Mock Neo4j query result
class MockResult:
    """Mock Neo4j query result."""

    def __init__(self, records: List[Dict[str, Any]]):
        self._records = records
        self._index = 0

    def __aiter__(self):
        """Async iterator."""
        return self

    async def __anext__(self):
        """Get next record."""
        if self._index >= len(self._records):
            raise StopAsyncIteration
        record = self._records[self._index]
        self._index += 1
        return record

    async def single(self):
        """Get single record."""
        if self._records:
            return self._records[0]
        return None


# Mock data matching exact Neo4j API response format
MOCK_LABELS_RESULT = MockResult([
    {"label": "Person"},
    {"label": "Company"},
    {"label": "Product"},
])

MOCK_PERSON_NODES = MockResult([
    {
        "n": MockNode(
            element_id="4:abc123:1",
            node_id=1,
            labels=["Person"],
            properties={
                "id": "person_001",
                "name": "John Doe",
                "email": "john@example.com",
                "age": 30,
                "active": True,
            },
        )
    },
    {
        "n": MockNode(
            element_id="4:abc123:2",
            node_id=2,
            labels=["Person"],
            properties={
                "id": "person_002",
                "name": "Jane Smith",
                "email": "jane@example.com",
                "age": 28,
                "active": True,
            },
        )
    },
])

MOCK_COMPANY_NODES = MockResult([
    {
        "n": MockNode(
            element_id="4:abc123:10",
            node_id=10,
            labels=["Company"],
            properties={
                "id": "company_001",
                "name": "Acme Corp",
                "industry": "Technology",
                "founded": 2010,
                "public": False,
            },
        )
    },
])

MOCK_PRODUCT_NODES = MockResult([
    {
        "n": MockNode(
            element_id="4:abc123:20",
            node_id=20,
            labels=["Product"],
            properties={
                "uuid": "prod-123-456",
                "name": "Widget Pro",
                "price": 99.99,
                "in_stock": True,
            },
        )
    },
])

# Mock for sampling nodes to infer properties
MOCK_PERSON_SAMPLE = MockResult([
    {
        "n": MockNode(
            element_id="4:abc123:1",
            node_id=1,
            labels=["Person"],
            properties={
                "id": "person_001",
                "name": "John Doe",
                "email": "john@example.com",
                "age": 30,
                "active": True,
            },
        )
    },
])

MOCK_COMPANY_SAMPLE = MockResult([
    {
        "n": MockNode(
            element_id="4:abc123:10",
            node_id=10,
            labels=["Company"],
            properties={
                "id": "company_001",
                "name": "Acme Corp",
                "industry": "Technology",
                "founded": 2010,
                "public": False,
            },
        )
    },
])

MOCK_PRODUCT_SAMPLE = MockResult([
    {
        "n": MockNode(
            element_id="4:abc123:20",
            node_id=20,
            labels=["Product"],
            properties={
                "uuid": "prod-123-456",
                "name": "Widget Pro",
                "price": 99.99,
                "in_stock": True,
            },
        )
    },
])

MOCK_VALIDATION_RESULT = MockResult([{"test": 1}])


@pytest.fixture
def mock_neo4j_driver():
    """Create a mock Neo4j async driver."""
    mock_driver = AsyncMock()
    mock_driver.verify_connectivity = AsyncMock()
    mock_driver.close = AsyncMock()

    # Mock session context manager
    mock_session = AsyncMock()
    mock_driver.session = MagicMock()
    mock_driver.session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_driver.session.return_value.__aexit__ = AsyncMock(return_value=None)

    return mock_driver, mock_session


@pytest.fixture
def neo4j_credentials():
    """Create test Neo4j credentials."""
    return {
        "uri": "neo4j://localhost:7687",
        "username": "neo4j",
        "password": "test12345",
    }


@pytest.mark.asyncio
async def test_neo4j_source_creation(neo4j_credentials):
    """Test Neo4j source instantiation."""
    source = await Neo4jSource.create(neo4j_credentials)

    assert source is not None
    assert source.config["uri"] == "neo4j://localhost:7687"
    assert source.config["username"] == "neo4j"
    assert source.config["password"] == "test12345"
    assert source.driver is None  # Not connected yet


@pytest.mark.asyncio
async def test_neo4j_source_connection(neo4j_credentials, mock_neo4j_driver):
    """Test Neo4j driver connection establishment."""
    mock_driver, _ = mock_neo4j_driver

    with patch("airweave.platform.sources.neo4j.AsyncGraphDatabase") as mock_graph_db:
        mock_graph_db.driver.return_value = mock_driver

        source = await Neo4jSource.create(neo4j_credentials)
        await source._connect()

        # Verify driver was created with correct URI
        mock_graph_db.driver.assert_called_once()
        call_args_str = str(mock_graph_db.driver.call_args)
        assert "neo4j://localhost:7687" in call_args_str
        assert "neo4j" in call_args_str  # username
        assert "test12345" in call_args_str  # password

        # Verify connectivity was tested
        mock_driver.verify_connectivity.assert_called_once()


@pytest.mark.asyncio
async def test_neo4j_source_validation(neo4j_credentials, mock_neo4j_driver):
    """Test Neo4j source validation."""
    mock_driver, mock_session = mock_neo4j_driver
    mock_session.run.return_value = MOCK_VALIDATION_RESULT

    with patch("airweave.platform.sources.neo4j.AsyncGraphDatabase") as mock_graph_db:
        mock_graph_db.driver.return_value = mock_driver

        source = await Neo4jSource.create(neo4j_credentials)
        is_valid = await source.validate()

        assert is_valid is True
        mock_session.run.assert_called_once_with("RETURN 1 AS test")
        mock_driver.close.assert_called_once()


@pytest.mark.asyncio
async def test_neo4j_get_node_labels(neo4j_credentials, mock_neo4j_driver):
    """Test retrieving all node labels from the database."""
    mock_driver, mock_session = mock_neo4j_driver
    mock_session.run.return_value = MOCK_LABELS_RESULT

    with patch("airweave.platform.sources.neo4j.AsyncGraphDatabase") as mock_graph_db:
        mock_graph_db.driver.return_value = mock_driver

        source = await Neo4jSource.create(neo4j_credentials)
        await source._connect()

        labels = await source._get_node_labels()

        assert len(labels) == 3
        assert "Person" in labels
        assert "Company" in labels
        assert "Product" in labels
        mock_session.run.assert_called_once_with("CALL db.labels()")


@pytest.mark.asyncio
async def test_neo4j_get_label_properties(neo4j_credentials, mock_neo4j_driver):
    """Test inferring property types from sample nodes."""
    mock_driver, mock_session = mock_neo4j_driver
    mock_session.run.return_value = MOCK_PERSON_SAMPLE

    with patch("airweave.platform.sources.neo4j.AsyncGraphDatabase") as mock_graph_db:
        mock_graph_db.driver.return_value = mock_driver

        source = await Neo4jSource.create(neo4j_credentials)
        await source._connect()

        properties = await source._get_label_properties("Person")

        assert "id" in properties
        assert properties["id"] == "String"
        assert "name" in properties
        assert properties["name"] == "String"
        assert "age" in properties
        assert properties["age"] == "Integer"
        assert "active" in properties
        assert properties["active"] == "Boolean"


@pytest.mark.asyncio
async def test_neo4j_entity_id_generation(neo4j_credentials):
    """Test entity ID generation from node properties."""
    source = await Neo4jSource.create(neo4j_credentials)

    # Test with 'id' property
    entity_id = source._generate_entity_id(
        "Person", 123, {"id": "person_001", "name": "John"}
    )
    assert entity_id == "neo4j:Person:person_001"

    # Test with 'uuid' property
    entity_id = source._generate_entity_id(
        "Product", 456, {"uuid": "prod-123", "name": "Widget"}
    )
    assert entity_id == "neo4j:Product:prod-123"

    # Test fallback to Neo4j internal ID
    entity_id = source._generate_entity_id(
        "Company", 789, {"name": "Acme Corp"}
    )
    assert entity_id == "neo4j:Company:789"


@pytest.mark.asyncio
async def test_neo4j_field_name_normalization(neo4j_credentials):
    """Test property name normalization to avoid collisions."""
    source = await Neo4jSource.create(neo4j_credentials)

    # Test 'id' gets normalized to 'id_'
    assert source._normalize_model_field_name("id") == "id_"

    # Test reserved fields get '_field' suffix
    assert source._normalize_model_field_name("entity_id") == "entity_id_field"
    assert source._normalize_model_field_name("breadcrumbs") == "breadcrumbs_field"
    assert source._normalize_model_field_name("name") == "name_field"  # 'name' is also reserved

    # Test normal fields stay unchanged
    assert source._normalize_model_field_name("email") == "email"
    assert source._normalize_model_field_name("age") == "age"


@pytest.mark.asyncio
async def test_neo4j_entity_class_creation(neo4j_credentials):
    """Test dynamic entity class creation for a label."""
    source = await Neo4jSource.create(neo4j_credentials)

    properties = {
        "id": "String",
        "name": "String",
        "email": "String",
        "age": "Integer",
        "active": "Boolean",
    }

    entity_class = await source._create_entity_class_for_label("Person", properties)

    assert entity_class is not None
    assert hasattr(entity_class, "model_fields")
    assert "id_" in entity_class.model_fields  # 'id' normalized to 'id_'
    assert "name" in entity_class.model_fields
    assert "email" in entity_class.model_fields
    assert "age" in entity_class.model_fields
    assert "active" in entity_class.model_fields


@pytest.mark.asyncio
async def test_neo4j_generate_entities_full_sync(neo4j_credentials, mock_neo4j_driver):
    """Test complete entity generation from all labels."""
    mock_driver, mock_session = mock_neo4j_driver

    # Setup mock responses for different queries
    def mock_run(query, *args, **kwargs):
        """Return appropriate mock result based on query."""
        if "CALL db.labels()" in query:
            return MockResult([
                {"label": "Person"},
                {"label": "Company"},
                {"label": "Product"},
            ])
        elif "MATCH (n:Person)" in query:
            if "LIMIT 100" in query:
                return MOCK_PERSON_SAMPLE
            else:
                return MOCK_PERSON_NODES
        elif "MATCH (n:Company)" in query:
            if "LIMIT 100" in query:
                return MOCK_COMPANY_SAMPLE
            else:
                return MOCK_COMPANY_NODES
        elif "MATCH (n:Product)" in query:
            if "LIMIT 100" in query:
                return MOCK_PRODUCT_SAMPLE
            else:
                return MOCK_PRODUCT_NODES
        # Default empty result
        return MockResult([])

    mock_session.run = AsyncMock(side_effect=mock_run)

    with patch("airweave.platform.sources.neo4j.AsyncGraphDatabase") as mock_graph_db:
        mock_graph_db.driver.return_value = mock_driver

        source = await Neo4jSource.create(neo4j_credentials)

        entities = []
        async for entity in source.generate_entities():
            entities.append(entity)

        # Verify we got entities from all labels
        # 2 Person + 1 Company + 1 Product = 4 entities
        assert len(entities) >= 3

        # Verify entity properties
        person_entities = [e for e in entities if "Person" in e.entity_id]
        assert len(person_entities) >= 1

        company_entities = [e for e in entities if "Company" in e.entity_id]
        assert len(company_entities) >= 1

        # Verify driver was closed
        mock_driver.close.assert_called()


@pytest.mark.asyncio
async def test_neo4j_connection_error_handling(neo4j_credentials):
    """Test error handling for connection failures."""
    with patch("airweave.platform.sources.neo4j.AsyncGraphDatabase") as mock_graph_db:
        # Simulate authentication error
        from neo4j.exceptions import AuthError

        mock_driver = AsyncMock()
        mock_driver.verify_connectivity.side_effect = AuthError("Invalid credentials")
        mock_graph_db.driver.return_value = mock_driver

        source = await Neo4jSource.create(neo4j_credentials)

        with pytest.raises(ValueError, match="Invalid Neo4j credentials"):
            await source._connect()


@pytest.mark.asyncio
async def test_neo4j_service_unavailable_error(neo4j_credentials):
    """Test error handling when Neo4j service is unavailable."""
    with patch("airweave.platform.sources.neo4j.AsyncGraphDatabase") as mock_graph_db:
        from neo4j.exceptions import ServiceUnavailable

        mock_driver = AsyncMock()
        mock_driver.verify_connectivity.side_effect = ServiceUnavailable(
            "Could not connect to database"
        )
        mock_graph_db.driver.return_value = mock_driver

        source = await Neo4jSource.create(neo4j_credentials)

        with pytest.raises(ValueError, match="Could not connect to Neo4j"):
            await source._connect()


@pytest.mark.asyncio
async def test_neo4j_validation_failure(neo4j_credentials, mock_neo4j_driver):
    """Test validation failure scenarios."""
    mock_driver, mock_session = mock_neo4j_driver
    mock_session.run.side_effect = Exception("Query failed")

    with patch("airweave.platform.sources.neo4j.AsyncGraphDatabase") as mock_graph_db:
        mock_graph_db.driver.return_value = mock_driver

        source = await Neo4jSource.create(neo4j_credentials)
        is_valid = await source.validate()

        assert is_valid is False
        mock_driver.close.assert_called_once()


@pytest.mark.asyncio
async def test_neo4j_entity_id_length_enforcement(neo4j_credentials):
    """Test entity ID length is enforced (max 2000 chars)."""
    source = await Neo4jSource.create(neo4j_credentials)

    # Create a very long entity ID
    long_id = "a" * 3000
    entity_id = source._ensure_entity_id_length(f"neo4j:Test:{long_id}", "Test")

    # Should be hashed to fit within limits
    assert len(entity_id) <= 2000
    assert "hashed_" in entity_id


@pytest.mark.asyncio
async def test_neo4j_empty_database(neo4j_credentials, mock_neo4j_driver):
    """Test handling of database with no labels."""
    mock_driver, mock_session = mock_neo4j_driver
    mock_session.run.return_value = MockResult([])  # No labels

    with patch("airweave.platform.sources.neo4j.AsyncGraphDatabase") as mock_graph_db:
        mock_graph_db.driver.return_value = mock_driver

        source = await Neo4jSource.create(neo4j_credentials)

        entities = []
        async for entity in source.generate_entities():
            entities.append(entity)

        # Should complete without errors
        assert len(entities) == 0
        mock_driver.close.assert_called_once()


def test_neo4j_auth_config_validation():
    """Test Neo4jAuthConfig validation."""
    from pydantic import ValidationError

    # Valid config
    config = Neo4jAuthConfig(
        uri="neo4j://localhost:7687",
        username="neo4j",
        password="test12345",
    )
    assert config.uri == "neo4j://localhost:7687"

    # Missing URI
    with pytest.raises(ValidationError):
        Neo4jAuthConfig(uri="", username="neo4j", password="test12345")

    # Missing username
    with pytest.raises(ValidationError):
        Neo4jAuthConfig(uri="neo4j://localhost:7687", username="", password="test12345")

    # Missing password
    with pytest.raises(ValidationError):
        Neo4jAuthConfig(uri="neo4j://localhost:7687", username="neo4j", password="")
