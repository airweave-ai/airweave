"""Unit tests for ChunkEmbedProcessor (simplified with mocks)."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from airweave.platform.sync.exceptions import SyncFailureError
from airweave.platform.sync.processors.chunk_embed import ChunkEmbedProcessor


@pytest.fixture
def processor():
    """Create ChunkEmbedProcessor instance."""
    return ChunkEmbedProcessor()


@pytest.fixture
def mock_sync_context():
    """Create mock SyncContext."""
    context = MagicMock()
    context.logger = MagicMock()
    context.collection = MagicMock()
    # Embedding config: None = never synced (first sync will stamp these)
    context.collection.embedding_model_name = None
    context.collection.vector_size = None
    return context


@pytest.fixture
def mock_runtime():
    """Create mock SyncRuntime with embedder service."""
    runtime = MagicMock()
    runtime.entity_tracker = AsyncMock()

    # Setup embedder service mock
    mock_dense_embedding = MagicMock()
    mock_dense_embedding.vector = [0.1] * 3072

    mock_sparse_embedding = MagicMock()
    mock_sparse_embedding.indices = [1, 2, 3]
    mock_sparse_embedding.values = [0.5, 0.3, 0.1]

    mock_dense_embedder = MagicMock()
    mock_dense_embedder.embed_many = AsyncMock(return_value=[mock_dense_embedding])

    mock_sparse_embedder = MagicMock()
    mock_sparse_embedder.embed_many = AsyncMock(return_value=[mock_sparse_embedding])

    mock_embedder_service = MagicMock()
    mock_embedder_service.vector_size = 3072
    mock_embedder_service.model_name = "test-model"
    mock_embedder_service.get_dense_embedder = MagicMock(return_value=mock_dense_embedder)
    mock_embedder_service.get_sparse_embedder = MagicMock(return_value=mock_sparse_embedder)

    runtime.embedder_service = mock_embedder_service
    runtime.collection_repo = AsyncMock()
    runtime.db_session = MagicMock()
    return runtime


@pytest.fixture
def mock_entity():
    """Create a simple mock entity."""
    entity = MagicMock()
    entity.entity_id = "test-123"
    entity.textual_representation = "Test content"
    entity.airweave_system_metadata = MagicMock()
    entity.airweave_system_metadata.chunk_index = None
    entity.airweave_system_metadata.original_entity_id = None
    entity.airweave_system_metadata.dense_embedding = None
    entity.airweave_system_metadata.sparse_embedding = None
    entity.model_copy = MagicMock(return_value=entity)
    return entity


class TestChunkEmbedProcessor:
    """Test ChunkEmbedProcessor chunks text and computes embeddings."""

    @pytest.mark.asyncio
    async def test_process_empty_list(self, processor, mock_sync_context, mock_runtime):
        """Test processing empty entity list returns empty."""
        result = await processor.process([], mock_sync_context, mock_runtime)
        assert result == []

    @pytest.mark.asyncio
    async def test_chunk_textual_entities_uses_semantic_chunker(
        self, processor, mock_sync_context, mock_runtime, mock_entity
    ):
        """Test textual entities routed to SemanticChunker."""
        with patch('airweave.platform.sync.processors.chunk_embed.text_builder') as mock_builder, \
             patch('airweave.platform.chunkers.semantic.SemanticChunker') as MockSemanticChunker, \
             patch.object(processor, '_embed_entities', new_callable=AsyncMock):

            # Setup mocks
            mock_builder.build_for_batch = AsyncMock(return_value=[mock_entity])
            mock_chunker = MockSemanticChunker.return_value
            mock_chunker.chunk_batch = AsyncMock(return_value=[
                [{"text": "Chunk 1"}, {"text": "Chunk 2"}]
            ])

            await processor.process([mock_entity], mock_sync_context, mock_runtime)

            # Verify SemanticChunker was called
            mock_chunker.chunk_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiply_entities_creates_chunk_suffix(
        self, processor, mock_sync_context
    ):
        """Test chunk entity creation with proper ID suffix."""
        # Create mock entity
        mock_entity = MagicMock()
        mock_entity.entity_id = "parent-123"
        mock_entity.textual_representation = "Original text"
        mock_entity.airweave_system_metadata = MagicMock()
        mock_entity.model_copy = MagicMock(return_value=MagicMock())

        # Configure model_copy to return new mock with modifiable attributes
        def create_chunk_entity(deep=False):
            chunk = MagicMock()
            chunk.entity_id = None
            chunk.textual_representation = None
            chunk.airweave_system_metadata = MagicMock()
            chunk.airweave_system_metadata.chunk_index = None
            chunk.airweave_system_metadata.original_entity_id = None
            return chunk

        mock_entity.model_copy = MagicMock(side_effect=create_chunk_entity)

        chunks = [
            [{"text": "Chunk 0"}, {"text": "Chunk 1"}]
        ]

        result = processor._multiply_entities([mock_entity], chunks, mock_sync_context)

        assert len(result) == 2
        # Check that entity IDs have chunk suffix
        assert "__chunk_0" in result[0].entity_id
        assert "__chunk_1" in result[1].entity_id

    @pytest.mark.asyncio
    async def test_multiply_entities_sets_chunk_index(
        self, processor, mock_sync_context
    ):
        """Test chunk index set correctly."""
        mock_entity = MagicMock()
        mock_entity.entity_id = "test-123"

        def create_chunk_entity(deep=False):
            chunk = MagicMock()
            chunk.entity_id = None
            chunk.textual_representation = None
            chunk.airweave_system_metadata = MagicMock()
            chunk.airweave_system_metadata.chunk_index = None
            chunk.airweave_system_metadata.original_entity_id = None
            return chunk

        mock_entity.model_copy = MagicMock(side_effect=create_chunk_entity)

        chunks = [[{"text": "Chunk"}]]

        result = processor._multiply_entities([mock_entity], chunks, mock_sync_context)

        assert result[0].airweave_system_metadata.chunk_index == 0

    @pytest.mark.asyncio
    async def test_multiply_entities_skips_empty_chunks(
        self, processor, mock_sync_context
    ):
        """Test empty chunks are filtered out."""
        mock_entity = MagicMock()
        mock_entity.entity_id = "test-123"

        def create_chunk_entity(deep=False):
            chunk = MagicMock()
            chunk.entity_id = None
            chunk.textual_representation = None
            chunk.airweave_system_metadata = MagicMock()
            chunk.airweave_system_metadata.chunk_index = None
            chunk.airweave_system_metadata.original_entity_id = None
            return chunk

        mock_entity.model_copy = MagicMock(side_effect=create_chunk_entity)

        chunks = [
            [{"text": "Valid"}, {"text": ""}, {"text": "  "}, {"text": "Another"}]
        ]

        result = processor._multiply_entities([mock_entity], chunks, mock_sync_context)

        # Should only have 2 chunks (empty ones filtered)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_embed_entities_calls_both_embedders(
        self, processor, mock_sync_context, mock_runtime
    ):
        """Test both dense and sparse embedders are called."""
        mock_entity = MagicMock()
        mock_entity.textual_representation = "Test content"
        mock_entity.airweave_system_metadata = MagicMock()
        mock_entity.model_dump = MagicMock(return_value={"entity_id": "test"})

        chunk_entities = [mock_entity]

        await processor._embed_entities(chunk_entities, mock_sync_context, mock_runtime)

        # Verify both embedders called
        dense_embedder = mock_runtime.embedder_service.get_dense_embedder()
        sparse_embedder = mock_runtime.embedder_service.get_sparse_embedder()
        dense_embedder.embed_many.assert_called_once()
        sparse_embedder.embed_many.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_entities_assigns_embeddings(
        self, processor, mock_sync_context, mock_runtime
    ):
        """Test embeddings assigned to entity system metadata."""
        mock_entity = MagicMock()
        mock_entity.textual_representation = "Test"
        mock_entity.airweave_system_metadata = MagicMock()
        mock_entity.airweave_system_metadata.dense_embedding = None
        mock_entity.airweave_system_metadata.sparse_embedding = None
        mock_entity.model_dump = MagicMock(return_value={"entity_id": "test"})

        chunk_entities = [mock_entity]

        await processor._embed_entities(chunk_entities, mock_sync_context, mock_runtime)

        # Check embeddings assigned
        assert mock_entity.airweave_system_metadata.dense_embedding == [0.1] * 3072
        assert mock_entity.airweave_system_metadata.sparse_embedding is not None

    @pytest.mark.asyncio
    async def test_embed_entities_uses_full_json_for_sparse(
        self, processor, mock_sync_context, mock_runtime
    ):
        """Test sparse embedder receives full entity JSON."""
        mock_entity = MagicMock()
        mock_entity.textual_representation = "Test"
        mock_entity.airweave_system_metadata = MagicMock()
        mock_entity.model_dump = MagicMock(return_value={
            "entity_id": "test-123",
            "name": "Test Entity",
        })

        chunk_entities = [mock_entity]

        await processor._embed_entities(chunk_entities, mock_sync_context, mock_runtime)

        # Verify sparse embedder got JSON strings
        sparse_embedder = mock_runtime.embedder_service.get_sparse_embedder()
        call_args = sparse_embedder.embed_many.call_args[0][0]
        assert isinstance(call_args, list)
        assert isinstance(call_args[0], str)

        # Verify it's JSON
        import json
        parsed = json.loads(call_args[0])
        assert "entity_id" in parsed

    @pytest.mark.asyncio
    async def test_embed_entities_validates_embeddings_exist(
        self, processor, mock_sync_context, mock_runtime
    ):
        """Test validation that all entities have embeddings."""
        mock_entity = MagicMock()
        mock_entity.textual_representation = "Test"
        mock_entity.entity_id = "test-123"
        mock_entity.airweave_system_metadata = MagicMock()
        mock_entity.model_dump = MagicMock(return_value={"entity_id": "test"})

        chunk_entities = [mock_entity]

        # Return None dense embedding
        mock_dense_embedding = MagicMock()
        mock_dense_embedding.vector = None

        dense_embedder = mock_runtime.embedder_service.get_dense_embedder()
        dense_embedder.embed_many = AsyncMock(return_value=[mock_dense_embedding])

        # Should raise error when assigning None vector
        with pytest.raises(Exception):
            await processor._embed_entities(chunk_entities, mock_sync_context, mock_runtime)

    @pytest.mark.asyncio
    async def test_full_pipeline_with_mocks(
        self, processor, mock_sync_context, mock_runtime
    ):
        """Test full pipeline with all mocked dependencies."""
        mock_entity = MagicMock()
        mock_entity.entity_id = "test-123"
        mock_entity.textual_representation = "Original text"
        mock_entity.airweave_system_metadata = MagicMock()

        def create_chunk(deep=False):
            chunk = MagicMock()
            chunk.entity_id = None
            chunk.textual_representation = None
            chunk.airweave_system_metadata = MagicMock()
            chunk.airweave_system_metadata.dense_embedding = None
            chunk.airweave_system_metadata.sparse_embedding = None
            chunk.model_dump = MagicMock(return_value={"entity_id": "chunk"})
            return chunk

        mock_entity.model_copy = MagicMock(side_effect=create_chunk)

        # Setup embedder to return 2 embeddings (one per chunk)
        mock_dense_1 = MagicMock()
        mock_dense_1.vector = [0.1] * 3072
        mock_dense_2 = MagicMock()
        mock_dense_2.vector = [0.2] * 3072

        dense_embedder = mock_runtime.embedder_service.get_dense_embedder()
        dense_embedder.embed_many = AsyncMock(return_value=[mock_dense_1, mock_dense_2])

        sparse_embedder = mock_runtime.embedder_service.get_sparse_embedder()
        sparse_embedder.embed_many = AsyncMock(return_value=[MagicMock(), MagicMock()])

        with patch('airweave.platform.sync.processors.chunk_embed.text_builder') as mock_builder, \
             patch('airweave.platform.chunkers.semantic.SemanticChunker') as MockChunker:

            # Setup mocks
            mock_builder.build_for_batch = AsyncMock(return_value=[mock_entity])

            mock_chunker = MockChunker.return_value
            mock_chunker.chunk_batch = AsyncMock(return_value=[
                [{"text": "Chunk 1"}, {"text": "Chunk 2"}]
            ])

            result = await processor.process([mock_entity], mock_sync_context, mock_runtime)

            # Should have 2 chunks
            assert len(result) == 2
            # Verify pipeline steps were called
            mock_builder.build_for_batch.assert_called_once()
            mock_chunker.chunk_batch.assert_called_once()
            dense_embedder.embed_many.assert_called_once()
            sparse_embedder.embed_many.assert_called_once()

    @pytest.mark.asyncio
    async def test_memory_optimization_clears_parent_text(
        self, processor, mock_sync_context, mock_runtime
    ):
        """Test parent entity text released after chunking."""
        mock_entity = MagicMock()
        mock_entity.entity_id = "test-123"
        mock_entity.textual_representation = "Original text"

        def create_chunk(deep=False):
            chunk = MagicMock()
            chunk.textual_representation = None
            chunk.airweave_system_metadata = MagicMock()
            chunk.model_dump = MagicMock(return_value={})
            return chunk

        mock_entity.model_copy = MagicMock(side_effect=create_chunk)

        with patch('airweave.platform.sync.processors.chunk_embed.text_builder') as mock_builder, \
             patch('airweave.platform.chunkers.semantic.SemanticChunker') as MockChunker:

            mock_builder.build_for_batch = AsyncMock(return_value=[mock_entity])

            mock_chunker = MockChunker.return_value
            mock_chunker.chunk_batch = AsyncMock(return_value=[[{"text": "Chunk"}]])

            await processor.process([mock_entity], mock_sync_context, mock_runtime)

            # Parent entity's textual_representation should be None
            assert mock_entity.textual_representation is None

    @pytest.mark.asyncio
    async def test_skips_entities_without_text(
        self, processor, mock_sync_context, mock_runtime
    ):
        """Test entities with no textual_representation are skipped."""
        mock_entity = MagicMock()
        mock_entity.entity_id = "test-123"
        mock_entity.textual_representation = None  # No text
        mock_entity.airweave_system_metadata = MagicMock()

        with patch('airweave.platform.sync.processors.chunk_embed.text_builder') as mock_builder:
            mock_builder.build_for_batch = AsyncMock(return_value=[mock_entity])

            result = await processor.process([mock_entity], mock_sync_context, mock_runtime)

            # Should return empty list (skipped)
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_handles_empty_chunks_from_chunker(
        self, processor, mock_sync_context, mock_runtime
    ):
        """Test handling when chunker returns empty list."""
        mock_entity = MagicMock()
        mock_entity.entity_id = "test-123"
        mock_entity.textual_representation = "Test"
        mock_entity.airweave_system_metadata = MagicMock()

        with patch('airweave.platform.sync.processors.chunk_embed.text_builder') as mock_builder, \
             patch('airweave.platform.chunkers.semantic.SemanticChunker') as MockChunker:

            mock_builder.build_for_batch = AsyncMock(return_value=[mock_entity])

            mock_chunker = MockChunker.return_value
            mock_chunker.chunk_batch = AsyncMock(return_value=[[]])  # Empty chunks

            result = await processor.process([mock_entity], mock_sync_context, mock_runtime)

            # Should skip entity with no chunks
            assert len(result) == 0


class TestEmbeddingConfigValidation:
    """Test embedding config stamp-on-first-sync and mismatch validation."""

    @pytest.mark.asyncio
    async def test_stamps_config_on_first_sync(self):
        """First sync stamps model+dims on collection."""
        processor = ChunkEmbedProcessor()
        sync_context = MagicMock()
        sync_context.collection.embedding_model_name = None
        sync_context.collection.vector_size = None
        sync_context.collection.id = UUID("00000000-0000-0000-0000-000000000001")
        sync_context.collection.readable_id = "test-collection"

        runtime = MagicMock()
        runtime.embedder_service.model_name = "text-embedding-3-small"
        runtime.embedder_service.vector_size = 1536
        runtime.collection_repo = AsyncMock()
        runtime.db_session = MagicMock()

        await processor._validate_and_stamp_embedding_config(sync_context, runtime)

        # Should have stamped via repo
        runtime.collection_repo.stamp_embedding_config.assert_called_once_with(
            runtime.db_session,
            collection_id=sync_context.collection.id,
            vector_size=1536,
            model_name="text-embedding-3-small",
        )
        # Should have updated in-memory collection
        assert sync_context.collection.embedding_model_name == "text-embedding-3-small"
        assert sync_context.collection.vector_size == 1536

    @pytest.mark.asyncio
    async def test_matching_config_passes(self):
        """Subsequent sync with same config passes silently."""
        processor = ChunkEmbedProcessor()
        sync_context = MagicMock()
        sync_context.collection.embedding_model_name = "text-embedding-3-small"
        sync_context.collection.vector_size = 1536

        runtime = MagicMock()
        runtime.embedder_service.model_name = "text-embedding-3-small"
        runtime.embedder_service.vector_size = 1536

        # Should not raise
        await processor._validate_and_stamp_embedding_config(sync_context, runtime)

    @pytest.mark.asyncio
    async def test_model_mismatch_raises(self):
        """Subsequent sync with different model raises SyncFailureError."""
        processor = ChunkEmbedProcessor()
        sync_context = MagicMock()
        sync_context.collection.embedding_model_name = "text-embedding-3-small"
        sync_context.collection.vector_size = 1536
        sync_context.collection.readable_id = "test-collection"

        runtime = MagicMock()
        runtime.embedder_service.model_name = "text-embedding-3-large"
        runtime.embedder_service.vector_size = 3072

        with pytest.raises(SyncFailureError, match="Embedding model mismatch"):
            await processor._validate_and_stamp_embedding_config(sync_context, runtime)

    @pytest.mark.asyncio
    async def test_dimension_mismatch_raises(self):
        """Subsequent sync with different dimensions raises SyncFailureError."""
        processor = ChunkEmbedProcessor()
        sync_context = MagicMock()
        sync_context.collection.embedding_model_name = "text-embedding-3-small"
        sync_context.collection.vector_size = 1536
        sync_context.collection.readable_id = "test-collection"

        runtime = MagicMock()
        runtime.embedder_service.model_name = "text-embedding-3-small"
        runtime.embedder_service.vector_size = 512

        with pytest.raises(SyncFailureError, match="Embedding dimensions mismatch"):
            await processor._validate_and_stamp_embedding_config(sync_context, runtime)

    @pytest.mark.asyncio
    async def test_skips_stamp_without_repo(self):
        """First sync without collection_repo skips DB stamp but updates in-memory."""
        processor = ChunkEmbedProcessor()
        sync_context = MagicMock()
        sync_context.collection.embedding_model_name = None
        sync_context.collection.vector_size = None

        runtime = MagicMock()
        runtime.embedder_service.model_name = "text-embedding-3-small"
        runtime.embedder_service.vector_size = 1536
        runtime.collection_repo = None
        runtime.db_session = None

        await processor._validate_and_stamp_embedding_config(sync_context, runtime)

        # Should still update in-memory
        assert sync_context.collection.embedding_model_name == "text-embedding-3-small"
        assert sync_context.collection.vector_size == 1536
