"""Unit tests for VespaDestination (orchestration layer)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from airweave.platform.destinations.vespa.destination import VespaDestination
from airweave.platform.destinations.vespa.types import FeedResult, VespaDocument
from airweave.schemas.search_result import AirweaveSearchResult, SystemMetadataResult


@pytest.fixture
def collection_id():
    """Sample collection ID."""
    return UUID("12345678-1234-1234-1234-123456789abc")


@pytest.fixture
def organization_id():
    """Sample organization ID."""
    return UUID("87654321-4321-4321-4321-cba987654321")


@pytest.fixture
def sync_id():
    """Sample sync ID."""
    return UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def mock_entity():
    """Create mock entity."""
    entity = MagicMock()
    entity.entity_id = "test-entity-123"
    entity.name = "Test Entity"
    entity.textual_representation = "Test content"
    return entity


class TestVespaDestination:
    """Test VespaDestination orchestration logic."""

    @pytest.mark.asyncio
    async def test_create_initializes_components(self, collection_id, organization_id):
        """Test create() initializes all components."""
        with patch('airweave.platform.destinations.vespa.destination.VespaClient') as MockClient, \
             patch('airweave.platform.destinations.vespa.destination.EntityTransformer') as MockTransformer, \
             patch('airweave.platform.destinations.vespa.destination.QueryBuilder') as MockBuilder:
            
            mock_client_instance = AsyncMock()
            MockClient.connect = AsyncMock(return_value=mock_client_instance)
            
            dest = await VespaDestination.create(
                collection_id=collection_id,
                organization_id=organization_id
            )
            
            assert dest._client == mock_client_instance
            assert dest.collection_id == collection_id
            assert dest.organization_id == organization_id
            MockClient.connect.assert_called_once()
            MockTransformer.assert_called_once()
            MockBuilder.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_with_soft_fail(self, collection_id):
        """Test create() with soft_fail enabled."""
        with patch('airweave.platform.destinations.vespa.destination.VespaClient.connect', new_callable=AsyncMock), \
             patch('airweave.platform.destinations.vespa.destination.EntityTransformer'), \
             patch('airweave.platform.destinations.vespa.destination.QueryBuilder'):
            
            dest = await VespaDestination.create(
                collection_id=collection_id,
                soft_fail=True
            )
            
            assert dest.soft_fail is True

    @pytest.mark.asyncio
    async def test_setup_collection_is_noop(self, collection_id):
        """Test setup_collection() is a no-op."""
        with patch('airweave.platform.destinations.vespa.destination.VespaClient.connect', new_callable=AsyncMock), \
             patch('airweave.platform.destinations.vespa.destination.EntityTransformer'), \
             patch('airweave.platform.destinations.vespa.destination.QueryBuilder'):
            
            dest = await VespaDestination.create(collection_id=collection_id)
            
            # Should not raise or do anything
            await dest.setup_collection(vector_size=3072)

    @pytest.mark.asyncio
    async def test_bulk_insert_empty_list(self, collection_id):
        """Test bulk_insert() with empty list."""
        with patch('airweave.platform.destinations.vespa.destination.VespaClient.connect', new_callable=AsyncMock), \
             patch('airweave.platform.destinations.vespa.destination.EntityTransformer'), \
             patch('airweave.platform.destinations.vespa.destination.QueryBuilder'):
            
            dest = await VespaDestination.create(collection_id=collection_id)
            
            # Should return early without error
            await dest.bulk_insert([])

    @pytest.mark.asyncio
    async def test_bulk_insert_transforms_and_feeds(self, collection_id, mock_entity):
        """Test bulk_insert() transforms entities and feeds to Vespa."""
        with patch('airweave.platform.destinations.vespa.destination.VespaClient.connect', new_callable=AsyncMock) as mock_connect, \
             patch('airweave.platform.destinations.vespa.destination.EntityTransformer') as MockTransformer, \
             patch('airweave.platform.destinations.vespa.destination.QueryBuilder'):
            
            # Setup mocks
            mock_client = AsyncMock()
            mock_connect.return_value = mock_client
            
            mock_transformer = MockTransformer.return_value
            mock_transformer.transform_batch.return_value = {
                "base_entity": [VespaDocument(schema="base_entity", id="test-1", fields={})]
            }
            
            feed_result = FeedResult(success_count=1, failed_docs=[])
            mock_client.feed_documents = AsyncMock(return_value=feed_result)
            
            dest = await VespaDestination.create(collection_id=collection_id)
            
            # Execute
            await dest.bulk_insert([mock_entity])
            
            # Verify
            mock_transformer.transform_batch.assert_called_once_with([mock_entity])
            mock_client.feed_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_bulk_insert_raises_on_uninitialized_client(self, mock_entity):
        """Test bulk_insert() raises if client not initialized."""
        dest = VespaDestination()
        dest._client = None
        
        with pytest.raises(RuntimeError) as exc_info:
            await dest.bulk_insert([mock_entity])
        
        assert "not initialized" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_bulk_insert_handles_feed_failures(self, collection_id, mock_entity):
        """Test bulk_insert() handles and logs feed failures."""
        with patch('airweave.platform.destinations.vespa.destination.VespaClient.connect', new_callable=AsyncMock) as mock_connect, \
             patch('airweave.platform.destinations.vespa.destination.EntityTransformer') as MockTransformer, \
             patch('airweave.platform.destinations.vespa.destination.QueryBuilder'):
            
            mock_client = AsyncMock()
            mock_connect.return_value = mock_client
            
            mock_transformer = MockTransformer.return_value
            mock_transformer.transform_batch.return_value = {
                "base_entity": [VespaDocument(schema="base_entity", id="test-1", fields={})]
            }
            
            # Simulate feed failure
            feed_result = FeedResult(
                success_count=0,
                failed_docs=[("doc-1", 500, {"error": "Internal error"})]
            )
            mock_client.feed_documents = AsyncMock(return_value=feed_result)
            
            dest = await VespaDestination.create(collection_id=collection_id)
            
            with pytest.raises(RuntimeError) as exc_info:
                await dest.bulk_insert([mock_entity])
            
            assert "Vespa feed failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_bulk_insert_skips_empty_transformation(self, collection_id, mock_entity):
        """Test bulk_insert() handles empty transformation result."""
        with patch('airweave.platform.destinations.vespa.destination.VespaClient.connect', new_callable=AsyncMock) as mock_connect, \
             patch('airweave.platform.destinations.vespa.destination.EntityTransformer') as MockTransformer, \
             patch('airweave.platform.destinations.vespa.destination.QueryBuilder'):
            
            mock_client = AsyncMock()
            mock_connect.return_value = mock_client
            
            mock_transformer = MockTransformer.return_value
            mock_transformer.transform_batch.return_value = {}  # No documents
            
            dest = await VespaDestination.create(collection_id=collection_id)
            
            # Should return without feeding
            await dest.bulk_insert([mock_entity])
            
            mock_client.feed_documents.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_by_sync_id(self, collection_id, sync_id):
        """Test delete_by_sync_id() calls client method."""
        with patch('airweave.platform.destinations.vespa.destination.VespaClient.connect', new_callable=AsyncMock) as mock_connect, \
             patch('airweave.platform.destinations.vespa.destination.EntityTransformer'), \
             patch('airweave.platform.destinations.vespa.destination.QueryBuilder'):
            
            mock_client = AsyncMock()
            mock_connect.return_value = mock_client
            mock_client.delete_by_sync_id = AsyncMock()
            
            dest = await VespaDestination.create(collection_id=collection_id)
            
            await dest.delete_by_sync_id(sync_id)
            
            mock_client.delete_by_sync_id.assert_called_once_with(sync_id, collection_id)

    @pytest.mark.asyncio
    async def test_delete_by_sync_id_raises_without_client(self, sync_id):
        """Test delete_by_sync_id() raises if client not initialized."""
        dest = VespaDestination()
        dest._client = None
        
        with pytest.raises(RuntimeError) as exc_info:
            await dest.delete_by_sync_id(sync_id)
        
        assert "not initialized" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_by_collection_id(self, collection_id):
        """Test delete_by_collection_id() calls client method."""
        with patch('airweave.platform.destinations.vespa.destination.VespaClient.connect', new_callable=AsyncMock) as mock_connect, \
             patch('airweave.platform.destinations.vespa.destination.EntityTransformer'), \
             patch('airweave.platform.destinations.vespa.destination.QueryBuilder'):
            
            mock_client = AsyncMock()
            mock_connect.return_value = mock_client
            mock_client.delete_by_collection_id = AsyncMock()
            
            dest = await VespaDestination.create(collection_id=collection_id)
            
            await dest.delete_by_collection_id(collection_id)
            
            mock_client.delete_by_collection_id.assert_called_once_with(collection_id)

    @pytest.mark.asyncio
    async def test_delete_by_collection_id_raises_without_client(self, collection_id):
        """Test delete_by_collection_id() raises if client not initialized."""
        dest = VespaDestination()
        dest._client = None
        
        with pytest.raises(RuntimeError):
            await dest.delete_by_collection_id(collection_id)

    @pytest.mark.asyncio
    async def test_bulk_delete_by_parent_ids(self, collection_id, sync_id):
        """Test bulk_delete_by_parent_ids() calls client method."""
        with patch('airweave.platform.destinations.vespa.destination.VespaClient.connect', new_callable=AsyncMock) as mock_connect, \
             patch('airweave.platform.destinations.vespa.destination.EntityTransformer'), \
             patch('airweave.platform.destinations.vespa.destination.QueryBuilder'):
            
            mock_client = AsyncMock()
            mock_connect.return_value = mock_client
            mock_client.delete_by_parent_ids = AsyncMock()
            
            dest = await VespaDestination.create(collection_id=collection_id)
            
            parent_ids = ["parent-1", "parent-2"]
            await dest.bulk_delete_by_parent_ids(parent_ids, sync_id)
            
            mock_client.delete_by_parent_ids.assert_called_once_with(parent_ids, collection_id)

    @pytest.mark.asyncio
    async def test_bulk_delete_by_parent_ids_empty_list(self, collection_id, sync_id):
        """Test bulk_delete_by_parent_ids() with empty list."""
        with patch('airweave.platform.destinations.vespa.destination.VespaClient.connect', new_callable=AsyncMock) as mock_connect, \
             patch('airweave.platform.destinations.vespa.destination.EntityTransformer'), \
             patch('airweave.platform.destinations.vespa.destination.QueryBuilder'):
            
            mock_client = AsyncMock()
            mock_connect.return_value = mock_client
            
            dest = await VespaDestination.create(collection_id=collection_id)
            
            # Should return without calling client
            await dest.bulk_delete_by_parent_ids([], sync_id)
            
            mock_client.delete_by_parent_ids.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_executes_query(self, collection_id):
        """Test search() builds query and executes search."""
        with patch('airweave.platform.destinations.vespa.destination.VespaClient.connect', new_callable=AsyncMock) as mock_connect, \
             patch('airweave.platform.destinations.vespa.destination.EntityTransformer'), \
             patch('airweave.platform.destinations.vespa.destination.QueryBuilder') as MockBuilder:
            
            mock_client = AsyncMock()
            mock_connect.return_value = mock_client
            
            mock_builder = MockBuilder.return_value
            mock_builder.build_yql.return_value = "select * from base_entity"
            mock_builder.build_params.return_value = {"hits": 10}
            
            mock_response = MagicMock()
            mock_response.hits = []
            mock_client.execute_query = AsyncMock(return_value=mock_response)
            mock_client.convert_hits_to_results = MagicMock(return_value=[])
            
            dest = await VespaDestination.create(collection_id=collection_id)
            
            results = await dest.search(
                queries=["test query"],
                airweave_collection_id=collection_id,
                limit=10,
                offset=0,
                dense_embeddings=[[0.1] * 3072],
                sparse_embeddings=[MagicMock()],
                retrieval_strategy="hybrid"
            )
            
            assert isinstance(results, list)
            mock_builder.build_yql.assert_called_once()
            mock_builder.build_params.assert_called_once()
            mock_client.execute_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_raises_without_client(self, collection_id):
        """Test search() raises if client not initialized."""
        dest = VespaDestination()
        dest._client = None
        
        with pytest.raises(RuntimeError):
            await dest.search(
                queries=["test"],
                airweave_collection_id=collection_id,
                limit=10,
                offset=0
            )

    @pytest.mark.asyncio
    async def test_search_validates_neural_embeddings(self, collection_id):
        """Test search() validates dense embeddings for neural search."""
        with patch('airweave.platform.destinations.vespa.destination.VespaClient.connect', new_callable=AsyncMock) as mock_connect, \
             patch('airweave.platform.destinations.vespa.destination.EntityTransformer'), \
             patch('airweave.platform.destinations.vespa.destination.QueryBuilder'):
            
            mock_client = AsyncMock()
            mock_connect.return_value = mock_client
            
            dest = await VespaDestination.create(collection_id=collection_id)
            
            with pytest.raises(ValueError) as exc_info:
                await dest.search(
                    queries=["test query"],
                    airweave_collection_id=collection_id,
                    limit=10,
                    offset=0,
                    retrieval_strategy="neural",
                    dense_embeddings=None  # Missing!
                )
            
            assert "dense embeddings" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_search_validates_keyword_embeddings(self, collection_id):
        """Test search() validates sparse embeddings for keyword search."""
        with patch('airweave.platform.destinations.vespa.destination.VespaClient.connect', new_callable=AsyncMock) as mock_connect, \
             patch('airweave.platform.destinations.vespa.destination.EntityTransformer'), \
             patch('airweave.platform.destinations.vespa.destination.QueryBuilder'):
            
            mock_client = AsyncMock()
            mock_connect.return_value = mock_client
            
            dest = await VespaDestination.create(collection_id=collection_id)
            
            with pytest.raises(ValueError) as exc_info:
                await dest.search(
                    queries=["test query"],
                    airweave_collection_id=collection_id,
                    limit=10,
                    offset=0,
                    retrieval_strategy="keyword",
                    sparse_embeddings=None  # Missing!
                )
            
            assert "sparse embeddings" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_search_validates_embedding_count(self, collection_id):
        """Test search() validates embedding count matches query count."""
        with patch('airweave.platform.destinations.vespa.destination.VespaClient.connect', new_callable=AsyncMock) as mock_connect, \
             patch('airweave.platform.destinations.vespa.destination.EntityTransformer'), \
             patch('airweave.platform.destinations.vespa.destination.QueryBuilder'):
            
            mock_client = AsyncMock()
            mock_connect.return_value = mock_client
            
            dest = await VespaDestination.create(collection_id=collection_id)
            
            with pytest.raises(ValueError) as exc_info:
                await dest.search(
                    queries=["query1", "query2"],  # 2 queries
                    airweave_collection_id=collection_id,
                    limit=10,
                    offset=0,
                    retrieval_strategy="neural",
                    dense_embeddings=[[0.1] * 3072],  # Only 1 embedding!
                    sparse_embeddings=[MagicMock(), MagicMock()]
                )
            
            assert "does not match" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_search_with_filter(self, collection_id):
        """Test search() with filter."""
        with patch('airweave.platform.destinations.vespa.destination.VespaClient.connect', new_callable=AsyncMock) as mock_connect, \
             patch('airweave.platform.destinations.vespa.destination.EntityTransformer'), \
             patch('airweave.platform.destinations.vespa.destination.QueryBuilder') as MockBuilder:
            
            mock_client = AsyncMock()
            mock_connect.return_value = mock_client
            
            mock_builder = MockBuilder.return_value
            mock_builder.build_yql.return_value = "select * from base_entity where ..."
            mock_builder.build_params.return_value = {"hits": 10}
            
            mock_response = MagicMock()
            mock_response.hits = []
            mock_client.execute_query = AsyncMock(return_value=mock_response)
            mock_client.convert_hits_to_results = MagicMock(return_value=[])
            
            dest = await VespaDestination.create(collection_id=collection_id)
            
            filter_dict = {"must": [{"key": "name", "match": {"value": "test"}}]}
            
            await dest.search(
                queries=["test query"],
                airweave_collection_id=collection_id,
                limit=10,
                offset=0,
                filter=filter_dict,
                dense_embeddings=[[0.1] * 3072],
                sparse_embeddings=[MagicMock()],
                retrieval_strategy="hybrid"
            )
            
            # Verify filter was passed
            call_args = mock_builder.build_yql.call_args
            assert call_args[0][2] == filter_dict

    @pytest.mark.asyncio
    async def test_search_with_multiple_queries(self, collection_id):
        """Test search() with query expansion."""
        with patch('airweave.platform.destinations.vespa.destination.VespaClient.connect', new_callable=AsyncMock) as mock_connect, \
             patch('airweave.platform.destinations.vespa.destination.EntityTransformer'), \
             patch('airweave.platform.destinations.vespa.destination.QueryBuilder') as MockBuilder:
            
            mock_client = AsyncMock()
            mock_connect.return_value = mock_client
            
            mock_builder = MockBuilder.return_value
            mock_builder.build_yql.return_value = "select * from base_entity"
            mock_builder.build_params.return_value = {"hits": 10}
            
            mock_response = MagicMock()
            mock_response.hits = []
            mock_client.execute_query = AsyncMock(return_value=mock_response)
            mock_client.convert_hits_to_results = MagicMock(return_value=[])
            
            dest = await VespaDestination.create(collection_id=collection_id)
            
            queries = ["query1", "query2", "query3"]
            await dest.search(
                queries=queries,
                airweave_collection_id=collection_id,
                limit=10,
                offset=0,
                dense_embeddings=[[0.1] * 3072] * 3,
                sparse_embeddings=[MagicMock()] * 3,
                retrieval_strategy="hybrid"
            )
            
            # Verify all queries were passed
            call_args = mock_builder.build_yql.call_args
            assert call_args[0][0] == queries

    def test_translate_filter(self, collection_id):
        """Test translate_filter() delegates to query builder."""
        with patch('airweave.platform.destinations.vespa.destination.QueryBuilder') as MockBuilder:
            mock_builder = MockBuilder.return_value
            mock_builder.filter_translator = MagicMock()
            mock_builder.filter_translator.translate.return_value = "name == 'test'"
            
            dest = VespaDestination()
            dest._query_builder = mock_builder
            
            filter_dict = {"must": [{"key": "name", "match": {"value": "test"}}]}
            result = dest.translate_filter(filter_dict)
            
            assert result == "name == 'test'"
            mock_builder.filter_translator.translate.assert_called_once_with(filter_dict)

    def test_translate_temporal_returns_none(self, collection_id):
        """Test translate_temporal() returns None (not implemented)."""
        dest = VespaDestination()
        
        from airweave.schemas.search import AirweaveTemporalConfig
        config = MagicMock(spec=AirweaveTemporalConfig)
        
        result = dest.translate_temporal(config)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_vector_config_names(self, collection_id):
        """Test get_vector_config_names() returns expected fields."""
        with patch('airweave.platform.destinations.vespa.destination.VespaClient.connect', new_callable=AsyncMock), \
             patch('airweave.platform.destinations.vespa.destination.EntityTransformer'), \
             patch('airweave.platform.destinations.vespa.destination.QueryBuilder'):
            
            dest = await VespaDestination.create(collection_id=collection_id)
            
            names = await dest.get_vector_config_names()
            
            assert names == ["dense_embedding"]

    @pytest.mark.asyncio
    async def test_close_connection(self, collection_id):
        """Test close_connection() closes client."""
        with patch('airweave.platform.destinations.vespa.destination.VespaClient.connect', new_callable=AsyncMock) as mock_connect, \
             patch('airweave.platform.destinations.vespa.destination.EntityTransformer'), \
             patch('airweave.platform.destinations.vespa.destination.QueryBuilder'):
            
            mock_client = AsyncMock()
            mock_connect.return_value = mock_client
            mock_client.close = AsyncMock()
            
            dest = await VespaDestination.create(collection_id=collection_id)
            
            await dest.close_connection()
            
            mock_client.close.assert_called_once()
            assert dest._client is None

    @pytest.mark.asyncio
    async def test_close_connection_without_client(self):
        """Test close_connection() when client is None."""
        dest = VespaDestination()
        dest._client = None
        
        # Should not raise
        await dest.close_connection()

