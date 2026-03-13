"""Unit tests for ChunkEmbedProcessor (simplified with mocks)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.domains.converters.fakes.registry import FakeConverterRegistry
from airweave.domains.sync_pipeline.processors.chunk_embed import ChunkEmbedProcessor

_TEXT_BUILDER_CLS = (
    "airweave.domains.sync_pipeline.processors.chunk_embed.TextualRepresentationBuilder"
)
_SEMANTIC_CHUNKER = "airweave.platform.chunkers.semantic.SemanticChunker"


@pytest.fixture
def processor():
    return ChunkEmbedProcessor(converter_registry=FakeConverterRegistry())


@pytest.fixture
def mock_sync_context():
    context = MagicMock()
    context.logger = MagicMock()
    context.collection = MagicMock()
    return context


@pytest.fixture
def mock_runtime():
    runtime = MagicMock()
    runtime.entity_tracker = AsyncMock()
    runtime.dense_embedder = MagicMock()
    runtime.dense_embedder.dimensions = 3072
    runtime.dense_embedder.embed_many = AsyncMock()
    runtime.sparse_embedder = MagicMock()
    runtime.sparse_embedder.embed_many = AsyncMock()
    return runtime


@pytest.fixture
def mock_entity():
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

    @pytest.mark.asyncio
    async def test_process_empty_list(self, processor, mock_sync_context, mock_runtime):
        result = await processor.process([], mock_sync_context, mock_runtime)
        assert result == []

    @pytest.mark.asyncio
    async def test_chunk_textual_entities_uses_semantic_chunker(
        self, processor, mock_sync_context, mock_runtime, mock_entity
    ):
        with (
            patch.object(
                processor._text_builder, "build_for_batch", new_callable=AsyncMock
            ) as mock_build,
            patch(_SEMANTIC_CHUNKER) as MockSemanticChunker,
            patch.object(processor, "_embed_entities", new_callable=AsyncMock),
        ):
            mock_build.return_value = [mock_entity]
            mock_chunker = MockSemanticChunker.return_value
            mock_chunker.chunk_batch = AsyncMock(
                return_value=[[{"text": "Chunk 1"}, {"text": "Chunk 2"}]]
            )

            await processor.process([mock_entity], mock_sync_context, mock_runtime)

            mock_chunker.chunk_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiply_entities_creates_chunk_suffix(self, processor, mock_sync_context):
        mock_entity = MagicMock()
        mock_entity.entity_id = "parent-123"
        mock_entity.textual_representation = "Original text"
        mock_entity.airweave_system_metadata = MagicMock()

        def create_chunk_entity(deep=False):
            chunk = MagicMock()
            chunk.entity_id = None
            chunk.textual_representation = None
            chunk.airweave_system_metadata = MagicMock()
            chunk.airweave_system_metadata.chunk_index = None
            chunk.airweave_system_metadata.original_entity_id = None
            return chunk

        mock_entity.model_copy = MagicMock(side_effect=create_chunk_entity)

        chunks = [[{"text": "Chunk 0"}, {"text": "Chunk 1"}]]
        result = processor._multiply_entities([mock_entity], chunks, mock_sync_context)

        assert len(result) == 2
        assert "__chunk_0" in result[0].entity_id
        assert "__chunk_1" in result[1].entity_id

    @pytest.mark.asyncio
    async def test_multiply_entities_sets_chunk_index(self, processor, mock_sync_context):
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
    async def test_multiply_entities_skips_empty_chunks(self, processor, mock_sync_context):
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

        chunks = [[{"text": "Valid"}, {"text": ""}, {"text": "  "}, {"text": "Another"}]]
        result = processor._multiply_entities([mock_entity], chunks, mock_sync_context)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_embed_entities_calls_both_embedders(self, processor, mock_runtime):
        mock_entity = MagicMock()
        mock_entity.textual_representation = "Test content"
        mock_entity.airweave_system_metadata = MagicMock()
        mock_entity.model_dump = MagicMock(return_value={"entity_id": "test"})

        dense_result = MagicMock()
        dense_result.vector = [0.1] * 3072
        mock_runtime.dense_embedder.embed_many = AsyncMock(return_value=[dense_result])
        mock_runtime.sparse_embedder.embed_many = AsyncMock(return_value=[MagicMock()])

        await processor._embed_entities([mock_entity], mock_runtime)

        mock_runtime.dense_embedder.embed_many.assert_called_once()
        mock_runtime.sparse_embedder.embed_many.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_entities_assigns_embeddings(self, processor, mock_runtime):
        mock_entity = MagicMock()
        mock_entity.textual_representation = "Test"
        mock_entity.airweave_system_metadata = MagicMock()
        mock_entity.airweave_system_metadata.dense_embedding = None
        mock_entity.airweave_system_metadata.sparse_embedding = None
        mock_entity.model_dump = MagicMock(return_value={"entity_id": "test"})

        dense_vector = [0.1] * 3072
        dense_result = MagicMock()
        dense_result.vector = dense_vector
        sparse_embedding = MagicMock()

        mock_runtime.dense_embedder.embed_many = AsyncMock(return_value=[dense_result])
        mock_runtime.sparse_embedder.embed_many = AsyncMock(return_value=[sparse_embedding])

        await processor._embed_entities([mock_entity], mock_runtime)

        assert mock_entity.airweave_system_metadata.dense_embedding == dense_vector
        assert mock_entity.airweave_system_metadata.sparse_embedding == sparse_embedding

    @pytest.mark.asyncio
    async def test_embed_entities_uses_full_json_for_sparse(self, processor, mock_runtime):
        mock_entity = MagicMock()
        mock_entity.textual_representation = "Test"
        mock_entity.airweave_system_metadata = MagicMock()
        mock_entity.model_dump = MagicMock(
            return_value={"entity_id": "test-123", "name": "Test Entity"}
        )

        dense_result = MagicMock()
        dense_result.vector = [0.1] * 3072
        mock_runtime.dense_embedder.embed_many = AsyncMock(return_value=[dense_result])
        mock_runtime.sparse_embedder.embed_many = AsyncMock(return_value=[MagicMock()])

        await processor._embed_entities([mock_entity], mock_runtime)

        call_args = mock_runtime.sparse_embedder.embed_many.call_args[0][0]
        assert isinstance(call_args, list)
        assert isinstance(call_args[0], str)

        import json

        parsed = json.loads(call_args[0])
        assert "entity_id" in parsed

    @pytest.mark.asyncio
    async def test_embed_entities_validates_embeddings_exist(self, processor, mock_runtime):
        mock_entity = MagicMock()
        mock_entity.textual_representation = "Test"
        mock_entity.entity_id = "test-123"
        mock_entity.airweave_system_metadata = MagicMock()
        mock_entity.model_dump = MagicMock(return_value={"entity_id": "test"})

        dense_result = MagicMock()
        dense_result.vector = None
        mock_runtime.dense_embedder.embed_many = AsyncMock(return_value=[dense_result])
        mock_runtime.sparse_embedder.embed_many = AsyncMock(return_value=[MagicMock()])

        with pytest.raises(Exception) as exc_info:
            await processor._embed_entities([mock_entity], mock_runtime)

        assert "no dense embedding" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_full_pipeline_with_mocks(self, processor, mock_sync_context, mock_runtime):
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

        dense_result = MagicMock()
        dense_result.vector = [0.1] * 3072
        dense_result_2 = MagicMock()
        dense_result_2.vector = [0.2] * 3072
        mock_runtime.dense_embedder.embed_many = AsyncMock(
            return_value=[dense_result, dense_result_2]
        )
        mock_runtime.sparse_embedder.embed_many = AsyncMock(return_value=[MagicMock(), MagicMock()])

        with (
            patch.object(
                processor._text_builder, "build_for_batch", new_callable=AsyncMock
            ) as mock_build,
            patch(_SEMANTIC_CHUNKER) as MockChunker,
        ):
            mock_build.return_value = [mock_entity]

            mock_chunker = MockChunker.return_value
            mock_chunker.chunk_batch = AsyncMock(
                return_value=[[{"text": "Chunk 1"}, {"text": "Chunk 2"}]]
            )

            result = await processor.process([mock_entity], mock_sync_context, mock_runtime)

            assert len(result) == 2
            mock_build.assert_called_once()
            mock_chunker.chunk_batch.assert_called_once()
            mock_runtime.dense_embedder.embed_many.assert_called_once()
            mock_runtime.sparse_embedder.embed_many.assert_called_once()

    @pytest.mark.asyncio
    async def test_memory_optimization_clears_parent_text(
        self, processor, mock_sync_context, mock_runtime
    ):
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

        dense_result = MagicMock()
        dense_result.vector = [0.1] * 3072
        mock_runtime.dense_embedder.embed_many = AsyncMock(return_value=[dense_result])
        mock_runtime.sparse_embedder.embed_many = AsyncMock(return_value=[MagicMock()])

        with (
            patch.object(
                processor._text_builder, "build_for_batch", new_callable=AsyncMock
            ) as mock_build,
            patch(_SEMANTIC_CHUNKER) as MockChunker,
        ):
            mock_build.return_value = [mock_entity]

            mock_chunker = MockChunker.return_value
            mock_chunker.chunk_batch = AsyncMock(return_value=[[{"text": "Chunk"}]])

            await processor.process([mock_entity], mock_sync_context, mock_runtime)

            assert mock_entity.textual_representation is None

    @pytest.mark.asyncio
    async def test_skips_entities_without_text(self, processor, mock_sync_context, mock_runtime):
        mock_entity = MagicMock()
        mock_entity.entity_id = "test-123"
        mock_entity.textual_representation = None
        mock_entity.airweave_system_metadata = MagicMock()

        with patch.object(
            processor._text_builder, "build_for_batch", new_callable=AsyncMock
        ) as mock_build:
            mock_build.return_value = [mock_entity]

            result = await processor.process([mock_entity], mock_sync_context, mock_runtime)

            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_handles_empty_chunks_from_chunker(
        self, processor, mock_sync_context, mock_runtime
    ):
        mock_entity = MagicMock()
        mock_entity.entity_id = "test-123"
        mock_entity.textual_representation = "Test"
        mock_entity.airweave_system_metadata = MagicMock()

        with (
            patch.object(
                processor._text_builder, "build_for_batch", new_callable=AsyncMock
            ) as mock_build,
            patch(_SEMANTIC_CHUNKER) as MockChunker,
        ):
            mock_build.return_value = [mock_entity]

            mock_chunker = MockChunker.return_value
            mock_chunker.chunk_batch = AsyncMock(return_value=[[]])

            result = await processor.process([mock_entity], mock_sync_context, mock_runtime)

            assert len(result) == 0
