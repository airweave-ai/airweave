"""Unit tests for ChunkEmbedProcessor (simplified with mocks)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.domains.converters.fakes.registry import FakeConverterRegistry
from airweave.domains.embedders.exceptions import EmbedderProviderError
from airweave.domains.sync_pipeline.processors.chunk_embed import ChunkEmbedProcessor

_TEXT_BUILDER_CLS = (
    "airweave.domains.sync_pipeline.processors.chunk_embed.TextualRepresentationBuilder"
)
_SEMANTIC_CHUNKER = "airweave.platform.chunkers.semantic.SemanticChunker"


@pytest.fixture
def mock_dense_embedder():
    embedder = MagicMock()
    embedder.dimensions = 3072
    embedder.embed_many = AsyncMock()
    return embedder


@pytest.fixture
def mock_sparse_embedder():
    embedder = MagicMock()
    embedder.embed_many = AsyncMock()
    return embedder


@pytest.fixture
def processor(mock_dense_embedder, mock_sparse_embedder):
    return ChunkEmbedProcessor(
        converter_registry=FakeConverterRegistry(),
        dense_embedder=mock_dense_embedder,
        sparse_embedder=mock_sparse_embedder,
    )


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
    async def test_embed_entities_calls_both_embedders(
        self, processor, mock_sync_context, mock_dense_embedder, mock_sparse_embedder
    ):
        mock_entity = MagicMock()
        mock_entity.textual_representation = "Test content"
        mock_entity.airweave_system_metadata = MagicMock()
        mock_entity.model_dump = MagicMock(return_value={"entity_id": "test"})

        dense_result = MagicMock()
        dense_result.vector = [0.1] * 3072
        mock_dense_embedder.embed_many = AsyncMock(return_value=[dense_result])
        mock_sparse_embedder.embed_many = AsyncMock(return_value=[MagicMock()])

        await processor._embed_entities([mock_entity], mock_sync_context)

        mock_dense_embedder.embed_many.assert_called_once()
        mock_sparse_embedder.embed_many.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_entities_assigns_embeddings(
        self, processor, mock_sync_context, mock_dense_embedder, mock_sparse_embedder
    ):
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

        mock_dense_embedder.embed_many = AsyncMock(return_value=[dense_result])
        mock_sparse_embedder.embed_many = AsyncMock(return_value=[sparse_embedding])

        await processor._embed_entities([mock_entity], mock_sync_context)

        assert mock_entity.airweave_system_metadata.dense_embedding == dense_vector
        assert mock_entity.airweave_system_metadata.sparse_embedding == sparse_embedding

    @pytest.mark.asyncio
    async def test_embed_entities_uses_full_json_for_sparse(
        self, processor, mock_sync_context, mock_dense_embedder, mock_sparse_embedder
    ):
        mock_entity = MagicMock()
        mock_entity.textual_representation = "Test"
        mock_entity.airweave_system_metadata = MagicMock()
        mock_entity.model_dump = MagicMock(
            return_value={"entity_id": "test-123", "name": "Test Entity"}
        )

        dense_result = MagicMock()
        dense_result.vector = [0.1] * 3072
        mock_dense_embedder.embed_many = AsyncMock(return_value=[dense_result])
        mock_sparse_embedder.embed_many = AsyncMock(return_value=[MagicMock()])

        await processor._embed_entities([mock_entity], mock_sync_context)

        call_args = mock_sparse_embedder.embed_many.call_args[0][0]
        assert isinstance(call_args, list)
        assert isinstance(call_args[0], str)

        import json

        parsed = json.loads(call_args[0])
        assert "entity_id" in parsed

    @pytest.mark.asyncio
    async def test_embed_entities_validates_embeddings_exist(
        self, processor, mock_sync_context, mock_dense_embedder, mock_sparse_embedder
    ):
        mock_entity = MagicMock()
        mock_entity.textual_representation = "Test"
        mock_entity.entity_id = "test-123"
        mock_entity.airweave_system_metadata = MagicMock()
        mock_entity.model_dump = MagicMock(return_value={"entity_id": "test"})

        dense_result = MagicMock()
        dense_result.vector = None
        mock_dense_embedder.embed_many = AsyncMock(return_value=[dense_result])
        mock_sparse_embedder.embed_many = AsyncMock(return_value=[MagicMock()])

        with pytest.raises(Exception) as exc_info:
            await processor._embed_entities([mock_entity], mock_sync_context)

        assert "no dense embedding" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_embed_entities_logs_error_on_dense_failure(
        self, processor, mock_sync_context, mock_dense_embedder
    ):
        """Test that dense embedding failure logs entity IDs and re-raises."""
        mock_entity = MagicMock()
        mock_entity.textual_representation = "Test"
        mock_entity.entity_id = "test-123"
        mock_entity.airweave_system_metadata = MagicMock()

        mock_dense_embedder.embed_many = AsyncMock(
            side_effect=RuntimeError("API error")
        )

        with pytest.raises(RuntimeError, match="API error"):
            await processor._embed_entities(
                [mock_entity], mock_sync_context
            )

        mock_sync_context.logger.error.assert_called_once()
        log_args = mock_sync_context.logger.error.call_args[0]
        assert "test-123" in str(log_args)

    @pytest.mark.asyncio
    async def test_full_pipeline_with_mocks(
        self, processor, mock_sync_context, mock_runtime, mock_dense_embedder, mock_sparse_embedder
    ):
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
        mock_dense_embedder.embed_many = AsyncMock(
            return_value=[dense_result, dense_result_2]
        )
        mock_sparse_embedder.embed_many = AsyncMock(return_value=[MagicMock(), MagicMock()])

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
            mock_dense_embedder.embed_many.assert_called_once()
            mock_sparse_embedder.embed_many.assert_called_once()

    @pytest.mark.asyncio
    async def test_memory_optimization_clears_parent_text(
        self, processor, mock_sync_context, mock_runtime, mock_dense_embedder, mock_sparse_embedder
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
        mock_dense_embedder.embed_many = AsyncMock(return_value=[dense_result])
        mock_sparse_embedder.embed_many = AsyncMock(return_value=[MagicMock()])

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
    async def test_embed_raises_when_textual_representation_is_none(
        self, processor, mock_sync_context, mock_dense_embedder
    ):
        from airweave.domains.sync_pipeline.exceptions import EntityProcessingError

        entity = MagicMock()
        entity.entity_id = "bad-chunk"
        entity.textual_representation = None
        entity.model_dump = MagicMock(return_value={})

        with pytest.raises(EntityProcessingError, match="no textual_representation"):
            await processor._embed_entities([entity], mock_sync_context)

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


# ---------------------------------------------------------------------------
# Dense embedding fallback tests
# ---------------------------------------------------------------------------


def _make_entity(entity_id: str, text: str = "Test content") -> MagicMock:
    """Create a mock entity with the minimum fields for embedding tests."""
    entity = MagicMock()
    entity.entity_id = entity_id
    entity.textual_representation = text
    entity.airweave_system_metadata = MagicMock()
    entity.airweave_system_metadata.dense_embedding = None
    entity.airweave_system_metadata.sparse_embedding = None
    entity.model_dump = MagicMock(return_value={"entity_id": entity_id})
    return entity


def _dense_result(dims: int = 3072) -> MagicMock:
    """Create a mock dense embedding result."""
    result = MagicMock()
    result.vector = [0.1] * dims
    return result


class TestDenseEmbedFallback:
    """Tests for the fallback-to-individual-embedding behavior."""

    @pytest.mark.asyncio
    async def test_non_retryable_error_falls_back_to_individual(
        self, processor, mock_sync_context, mock_dense_embedder, mock_sparse_embedder
    ):
        """When batch embed raises a non-retryable EmbedderProviderError,
        fall back to embedding one-by-one."""
        e1 = _make_entity("good-1")
        e2 = _make_entity("bad-1")

        # First call (batch) fails, individual calls: good-1 succeeds, bad-1 fails
        mock_dense_embedder.embed_many = AsyncMock(
            side_effect=[
                EmbedderProviderError("bad JSON", provider="openai", retryable=False),
                [_dense_result()],  # good-1 individually
                EmbedderProviderError("bad JSON", provider="openai", retryable=False),
            ]
        )
        mock_sparse_embedder.embed_many = AsyncMock(return_value=[MagicMock()])

        result = await processor._embed_entities([e1, e2], mock_sync_context)

        assert len(result) == 1
        assert result[0].entity_id == "good-1"
        mock_sync_context.logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_retryable_error_still_raises(
        self, processor, mock_sync_context, mock_dense_embedder
    ):
        """Retryable errors (e.g. 500s) should NOT trigger fallback."""
        e1 = _make_entity("test-1")
        mock_dense_embedder.embed_many = AsyncMock(
            side_effect=EmbedderProviderError("server error", provider="openai", retryable=True)
        )

        with pytest.raises(EmbedderProviderError, match="server error"):
            await processor._embed_entities([e1], mock_sync_context)

    @pytest.mark.asyncio
    async def test_non_provider_error_still_raises(
        self, processor, mock_sync_context, mock_dense_embedder
    ):
        """Non-EmbedderProviderError exceptions should NOT trigger fallback."""
        e1 = _make_entity("test-1")
        mock_dense_embedder.embed_many = AsyncMock(
            side_effect=RuntimeError("unexpected")
        )

        with pytest.raises(RuntimeError, match="unexpected"):
            await processor._embed_entities([e1], mock_sync_context)

    @pytest.mark.asyncio
    async def test_all_entities_fail_individually_returns_empty(
        self, processor, mock_sync_context, mock_dense_embedder
    ):
        """When every entity fails during individual fallback, return empty list."""
        e1 = _make_entity("bad-1")
        e2 = _make_entity("bad-2")

        mock_dense_embedder.embed_many = AsyncMock(
            side_effect=EmbedderProviderError("bad JSON", provider="openai", retryable=False)
        )

        result = await processor._embed_entities([e1, e2], mock_sync_context)

        assert result == []

    @pytest.mark.asyncio
    async def test_fallback_logs_skipped_entity_ids(
        self, processor, mock_sync_context, mock_dense_embedder, mock_sparse_embedder
    ):
        """Skipped entities should be logged with their entity IDs."""
        e1 = _make_entity("good-1")
        e2 = _make_entity("bad-1")

        mock_dense_embedder.embed_many = AsyncMock(
            side_effect=[
                EmbedderProviderError("bad JSON", provider="openai", retryable=False),
                [_dense_result()],  # good-1
                EmbedderProviderError("bad JSON", provider="openai", retryable=False),
            ]
        )
        mock_sparse_embedder.embed_many = AsyncMock(return_value=[MagicMock()])

        await processor._embed_entities([e1, e2], mock_sync_context)

        # Check that warning logs mention the bad entity ID
        warning_calls = mock_sync_context.logger.warning.call_args_list
        all_warning_text = " ".join(
            " ".join(str(a) for a in call.args) for call in warning_calls
        )
        assert "bad-1" in all_warning_text
        assert "Skipping entity" in all_warning_text

    @pytest.mark.asyncio
    async def test_batch_success_does_not_trigger_fallback(
        self, processor, mock_sync_context, mock_dense_embedder, mock_sparse_embedder
    ):
        """Happy path: batch embed succeeds, no fallback needed."""
        e1 = _make_entity("ok-1")
        e2 = _make_entity("ok-2")

        mock_dense_embedder.embed_many = AsyncMock(
            return_value=[_dense_result(), _dense_result()]
        )
        mock_sparse_embedder.embed_many = AsyncMock(
            return_value=[MagicMock(), MagicMock()]
        )

        result = await processor._embed_entities([e1, e2], mock_sync_context)

        assert len(result) == 2
        # embed_many called exactly once (batch), not per-entity
        assert mock_dense_embedder.embed_many.call_count == 1
