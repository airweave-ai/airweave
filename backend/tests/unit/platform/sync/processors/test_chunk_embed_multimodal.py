"""Unit tests for ChunkEmbedProcessor multimodal pipeline routing."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.domains.embedders.exceptions import EmbedderInputError
from airweave.domains.embedders.protocols import EmbeddingPurpose
from airweave.domains.embedders.types import DenseEmbedding, SparseEmbedding
from airweave.platform.sync.processors.chunk_embed import ChunkEmbedProcessor


@pytest.fixture
def processor():
    return ChunkEmbedProcessor()


@pytest.fixture
def mock_sync_context():
    context = MagicMock()
    context.logger = MagicMock()
    context.collection = MagicMock()
    return context


def _make_multimodal_runtime(supported_mimes=None):
    """Create a mock runtime with a multimodal-capable dense embedder."""
    if supported_mimes is None:
        supported_mimes = {"image/png", "image/jpeg", "application/pdf"}

    runtime = MagicMock()
    runtime.entity_tracker = AsyncMock()

    # Dense embedder that satisfies MultimodalDenseEmbedderProtocol
    embedder = MagicMock()
    embedder.dimensions = 256
    embedder.supports_multimodal = True
    embedder.supported_mime_types = supported_mimes
    embedder.embed_many = AsyncMock(
        return_value=[DenseEmbedding(vector=[0.0] * 256)]
    )
    embedder.embed_file = AsyncMock(
        return_value=DenseEmbedding(vector=[0.0] * 256)
    )
    runtime.dense_embedder = embedder

    runtime.sparse_embedder = MagicMock()
    runtime.sparse_embedder.embed_many = AsyncMock(
        return_value=[SparseEmbedding(indices=[0], values=[1.0])]
    )

    return runtime


def _make_text_only_runtime():
    """Create a mock runtime with a text-only dense embedder."""
    runtime = MagicMock()
    runtime.entity_tracker = AsyncMock()

    embedder = MagicMock()
    embedder.dimensions = 256
    # Not multimodal — no supports_multimodal attribute
    embedder.embed_many = AsyncMock(
        return_value=[DenseEmbedding(vector=[0.0] * 256)]
    )
    runtime.dense_embedder = embedder

    runtime.sparse_embedder = MagicMock()
    runtime.sparse_embedder.embed_many = AsyncMock(
        return_value=[SparseEmbedding(indices=[0], values=[1.0])]
    )

    return runtime


def _make_file_entity(entity_id="file-1", mime_type="image/png", local_path="/tmp/test.png"):
    """Create a mock FileEntity."""
    from airweave.platform.entities._base import FileEntity

    entity = MagicMock(spec=FileEntity)
    entity.entity_id = entity_id
    entity.mime_type = mime_type
    entity.local_path = local_path
    entity.textual_representation = "Extracted text from file"
    entity.airweave_system_metadata = MagicMock()
    entity.airweave_system_metadata.chunk_index = None
    entity.airweave_system_metadata.original_entity_id = None
    entity.airweave_system_metadata.dense_embedding = None
    entity.airweave_system_metadata.sparse_embedding = None
    entity.model_copy = MagicMock(return_value=MagicMock(
        entity_id=entity_id,
        textual_representation="Extracted text from file",
        airweave_system_metadata=MagicMock(
            chunk_index=None,
            original_entity_id=None,
            dense_embedding=None,
            sparse_embedding=None,
        ),
        model_dump=MagicMock(return_value={"entity_id": entity_id}),
    ))
    entity.model_dump = MagicMock(return_value={"entity_id": entity_id})
    return entity


def _make_base_entity(entity_id="text-1"):
    """Create a mock BaseEntity (not FileEntity)."""
    from airweave.platform.entities._base import BaseEntity

    entity = MagicMock(spec=BaseEntity)
    entity.entity_id = entity_id
    entity.textual_representation = "Some text"
    entity.airweave_system_metadata = MagicMock()
    return entity


# ---------------------------------------------------------------------------
# Partitioning tests
# ---------------------------------------------------------------------------


class TestPartitionByEmbeddingMode:
    def test_non_multimodal_embedder_routes_all_to_text(self, processor):
        """Non-multimodal embedder -> all entities go to text pipeline."""
        runtime = _make_text_only_runtime()
        file_entity = _make_file_entity()

        native, text = processor._partition_by_embedding_mode([file_entity], runtime)

        assert len(native) == 0
        assert len(text) == 1

    def test_multimodal_embedder_routes_eligible_files(self, processor):
        """FileEntity with supported MIME + multimodal embedder -> native list."""
        from airweave.domains.embedders.fakes.embedder import FakeMultimodalDenseEmbedder

        runtime = _make_multimodal_runtime()
        # Use the real FakeMultimodalDenseEmbedder so isinstance() works
        runtime.dense_embedder = FakeMultimodalDenseEmbedder(dimensions=256)

        file_entity = _make_file_entity(mime_type="image/png")

        with patch(
            "airweave.core.config.settings",
            MagicMock(ENABLE_MEDIA_SYNC=False),
        ):
            native, text = processor._partition_by_embedding_mode(
                [file_entity], runtime
            )

        # image/png is not a media MIME, so it goes native regardless of flag
        assert len(native) == 1
        assert len(text) == 0

    def test_non_file_entity_goes_to_text(self, processor):
        """Non-FileEntity always goes to text pipeline regardless of embedder."""
        runtime = _make_multimodal_runtime()
        base_entity = _make_base_entity()

        native, text = processor._partition_by_embedding_mode([base_entity], runtime)

        assert len(native) == 0
        assert len(text) == 1

    def test_file_entity_without_mime_goes_to_text(self, processor):
        """FileEntity without mime_type goes to text pipeline."""
        runtime = _make_multimodal_runtime()
        file_entity = _make_file_entity(mime_type=None)

        native, text = processor._partition_by_embedding_mode([file_entity], runtime)

        assert len(native) == 0
        assert len(text) == 1

    def test_file_entity_without_local_path_goes_to_text(self, processor):
        """FileEntity without local_path goes to text pipeline."""
        runtime = _make_multimodal_runtime()
        file_entity = _make_file_entity(local_path=None)

        native, text = processor._partition_by_embedding_mode([file_entity], runtime)

        assert len(native) == 0
        assert len(text) == 1

    def test_file_entity_unsupported_mime_goes_to_text(self, processor):
        """FileEntity with unsupported MIME type goes to text pipeline."""
        runtime = _make_multimodal_runtime(supported_mimes={"image/png"})
        file_entity = _make_file_entity(mime_type="text/plain")

        native, text = processor._partition_by_embedding_mode([file_entity], runtime)

        assert len(native) == 0
        assert len(text) == 1

    def test_mixed_entities_partition_correctly(self, processor):
        """Mix of FileEntity and BaseEntity partitions correctly."""
        runtime = _make_multimodal_runtime()
        file_entity = _make_file_entity(mime_type="image/png")
        base_entity = _make_base_entity()

        native, text = processor._partition_by_embedding_mode(
            [file_entity, base_entity], runtime
        )

        assert len(native) == 1
        assert len(text) == 1

    def test_media_gated_by_enable_media_sync(self, processor):
        """Audio/video entities go to text when ENABLE_MEDIA_SYNC=False."""
        runtime = _make_multimodal_runtime(
            supported_mimes={"image/png", "audio/mpeg", "video/mp4"}
        )
        audio_entity = _make_file_entity(mime_type="audio/mpeg")
        video_entity = _make_file_entity(mime_type="video/mp4", entity_id="vid-1")
        image_entity = _make_file_entity(mime_type="image/png", entity_id="img-1")

        with patch(
            "airweave.core.config.settings",
            MagicMock(ENABLE_MEDIA_SYNC=False),
        ):
            native, text = processor._partition_by_embedding_mode(
                [audio_entity, video_entity, image_entity], runtime
            )

        # Audio + video should go to text, image to native
        assert len(native) == 1  # only image
        assert len(text) == 2    # audio + video


# ---------------------------------------------------------------------------
# Native multimodal pipeline tests
# ---------------------------------------------------------------------------


class TestNativeMultimodalPipeline:
    @pytest.mark.asyncio
    async def test_native_pipeline_produces_one_chunk(self, processor, mock_sync_context):
        runtime = _make_multimodal_runtime()
        file_entity = _make_file_entity()

        with patch.object(
            processor, "_native_multimodal_pipeline"
        ) as mock_native, patch.object(
            processor, "_text_pipeline"
        ) as mock_text, patch.object(
            processor, "_partition_by_embedding_mode",
            return_value=([file_entity], []),
        ):
            mock_native.return_value = [MagicMock()]
            mock_text.return_value = []

            result = await processor.process([file_entity], mock_sync_context, runtime)

            mock_native.assert_called_once()
            mock_text.assert_not_called()
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_text_pipeline_called_for_non_multimodal(self, processor, mock_sync_context):
        runtime = _make_text_only_runtime()
        base_entity = _make_base_entity()

        with patch.object(
            processor, "_native_multimodal_pipeline"
        ) as mock_native, patch.object(
            processor, "_text_pipeline"
        ) as mock_text, patch.object(
            processor, "_partition_by_embedding_mode",
            return_value=([], [base_entity]),
        ):
            mock_native.return_value = []
            mock_text.return_value = [MagicMock()]

            result = await processor.process([base_entity], mock_sync_context, runtime)

            mock_native.assert_not_called()
            mock_text.assert_called_once()
            assert len(result) == 1


class TestNativeEmbeddingDecoupledFromText:
    """Verify native embedding works even when text extraction fails."""

    @pytest.mark.asyncio
    async def test_entity_with_empty_text_still_gets_dense_embedding(
        self, processor, mock_sync_context
    ):
        """An entity with empty textual_representation should still get
        a dense embedding via embed_file() — text is best-effort."""
        runtime = _make_multimodal_runtime()
        file_entity = _make_file_entity(mime_type="image/png")
        file_entity.textual_representation = None  # OCR failed

        with patch(
            "airweave.platform.sync.processors.chunk_embed.text_builder"
        ) as mock_tb:
            # Simulate text_builder returning entity with no text
            mock_tb.build_for_batch = AsyncMock(return_value=[file_entity])

            result = await processor._native_multimodal_pipeline(
                [file_entity], mock_sync_context, runtime
            )

        # Should still produce a chunk with dense embedding
        assert len(result) >= 1
        runtime.dense_embedder.embed_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_text_gets_placeholder_for_sparse(
        self, processor, mock_sync_context
    ):
        """Entities with no text get a filename placeholder for sparse scoring."""
        runtime = _make_multimodal_runtime()
        file_entity = _make_file_entity(
            mime_type="image/png", local_path="/data/photo.png"
        )
        file_entity.textual_representation = ""  # Empty

        with patch(
            "airweave.platform.sync.processors.chunk_embed.text_builder"
        ) as mock_tb:
            mock_tb.build_for_batch = AsyncMock(return_value=[file_entity])

            chunks = await processor._native_multimodal_pipeline(
                [file_entity], mock_sync_context, runtime
            )

        # Should still produce chunks despite empty text
        assert len(chunks) >= 1
        # Sparse embedding should have been computed (not skipped)
        runtime.sparse_embedder.embed_many.assert_called_once()


class TestNativeMultimodalPipelineFallback:
    @pytest.mark.asyncio
    async def test_fallback_on_embedder_input_error(self, processor, mock_sync_context):
        """embed_file raising EmbedderInputError triggers text pipeline fallback."""
        runtime = _make_multimodal_runtime()
        runtime.dense_embedder.embed_file = AsyncMock(
            side_effect=EmbedderInputError("too many pages")
        )
        file_entity = _make_file_entity()

        with patch(
            "airweave.platform.sync.processors.chunk_embed.text_builder"
        ) as mock_tb, patch(
            "airweave.platform.sync.processors.chunk_embed.filter_empty_representations",
            new_callable=AsyncMock,
            return_value=[file_entity],
        ), patch.object(
            processor, "_text_pipeline",
            new_callable=AsyncMock,
            return_value=[MagicMock()],
        ) as mock_text:
            mock_tb.build_for_batch = AsyncMock(return_value=[file_entity])

            result = await processor._native_multimodal_pipeline(
                [file_entity], mock_sync_context, runtime
            )

            # Fallback to text pipeline should have been called
            mock_text.assert_called_once()


# ---------------------------------------------------------------------------
# Process empty list
# ---------------------------------------------------------------------------


class TestProcessEmpty:
    @pytest.mark.asyncio
    async def test_empty_list(self, processor, mock_sync_context):
        runtime = _make_text_only_runtime()
        result = await processor.process([], mock_sync_context, runtime)
        assert result == []
