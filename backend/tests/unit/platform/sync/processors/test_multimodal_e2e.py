"""End-to-end tests for the multimodal embedding pipeline using synthetic media.

Generates real PDF, audio, and video test fixtures programmatically:
- PDF: PyMuPDF (fitz) with known text per page
- Audio: pydub sine wave tone (no ffmpeg needed for generation)
- Video: ffmpeg lavfi test pattern

All Gemini API calls are mocked — these tests verify the full pipeline
routing, chunking, and fallback logic with real file I/O.
"""

import asyncio
import math
import os
import shutil
import struct
import tempfile
import wave
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import fitz  # PyMuPDF
import pytest

from airweave.domains.embedders.exceptions import EmbedderInputError
from airweave.domains.embedders.protocols import EmbeddingPurpose
from airweave.domains.embedders.types import DenseEmbedding, SparseEmbedding


# ---------------------------------------------------------------------------
# Fixture generators
# ---------------------------------------------------------------------------

DIMS = 256


def generate_pdf(path: str, num_pages: int, text_per_page: str = "Page {n} content.") -> str:
    """Create a real PDF with known text on each page."""
    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page(width=612, height=792)
        text = text_per_page.format(n=i + 1)
        page.insert_text((72, 72), text, fontsize=12)
    doc.save(path)
    doc.close()
    return path


def generate_wav(path: str, duration_seconds: float, frequency: int = 440) -> str:
    """Create a real WAV file with a sine wave tone. No external deps."""
    sample_rate = 16000
    num_samples = int(sample_rate * duration_seconds)
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(num_samples):
            value = int(32767 * math.sin(2 * math.pi * frequency * i / sample_rate))
            wf.writeframes(struct.pack("<h", value))
    return path


def generate_mp4(path: str, duration_seconds: float) -> str | None:
    """Create a real MP4 with ffmpeg test pattern. Returns None if no ffmpeg."""
    if not shutil.which("ffmpeg"):
        return None
    import subprocess

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"testsrc=duration={duration_seconds}:size=320x240:rate=10",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration_seconds}",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "32k",
            "-shortest",
            path,
        ],
        capture_output=True,
        timeout=30,
    )
    return path if os.path.exists(path) else None


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _mock_embed_result() -> DenseEmbedding:
    """Return a deterministic non-zero embedding."""
    vector = [float(i % 7) / 7.0 for i in range(DIMS)]
    return DenseEmbedding(vector=vector)


def _make_file_entity(entity_id: str, local_path: str, mime_type: str, file_type: str):
    """Create a real-ish FileEntity mock with actual file properties."""
    from airweave.platform.entities._base import FileEntity

    entity = MagicMock(spec=FileEntity)
    entity.entity_id = entity_id
    entity.local_path = local_path
    entity.mime_type = mime_type
    entity.file_type = file_type
    entity.url = f"file://{local_path}"
    entity.size = os.path.getsize(local_path)
    entity.textual_representation = None
    entity.airweave_system_metadata = MagicMock()
    entity.airweave_system_metadata.chunk_index = None
    entity.airweave_system_metadata.original_entity_id = None
    entity.airweave_system_metadata.dense_embedding = None
    entity.airweave_system_metadata.sparse_embedding = None

    def make_copy(deep=False):
        copy = MagicMock(spec=FileEntity)
        copy.entity_id = entity.entity_id
        copy.local_path = entity.local_path
        copy.mime_type = entity.mime_type
        copy.textual_representation = entity.textual_representation
        copy.airweave_system_metadata = MagicMock()
        copy.airweave_system_metadata.chunk_index = None
        copy.airweave_system_metadata.original_entity_id = None
        copy.airweave_system_metadata.dense_embedding = None
        copy.airweave_system_metadata.sparse_embedding = None
        copy.model_dump = MagicMock(return_value={"entity_id": entity.entity_id})
        copy.model_copy = make_copy
        return copy

    entity.model_copy = make_copy
    entity.model_dump = MagicMock(return_value={"entity_id": entity_id})
    return entity


def _make_multimodal_runtime():
    runtime = MagicMock()
    runtime.entity_tracker = AsyncMock()

    embedder = MagicMock()
    embedder.dimensions = DIMS
    embedder.supports_multimodal = True
    embedder.supported_mime_types = {
        "image/png", "image/jpeg", "application/pdf",
        "audio/mpeg", "audio/wav", "video/mp4",
    }
    embedder.embed_many = AsyncMock(return_value=[_mock_embed_result()])
    embedder.embed_file = AsyncMock(return_value=_mock_embed_result())
    embedder.embed_file_parts = AsyncMock(return_value=_mock_embed_result())
    runtime.dense_embedder = embedder

    runtime.sparse_embedder = MagicMock()
    runtime.sparse_embedder.embed_many = AsyncMock(
        return_value=[SparseEmbedding(indices=[0, 1], values=[0.5, 0.5])]
    )
    return runtime


# ---------------------------------------------------------------------------
# E2E: PDF
# ---------------------------------------------------------------------------


class TestPdfE2E:
    """Test real PDFs through the multimodal pipeline."""

    @pytest.mark.asyncio
    async def test_small_pdf_single_chunk(self, tmp_path):
        """A 3-page PDF (under limit) produces 1 native chunk."""
        pdf_path = generate_pdf(str(tmp_path / "small.pdf"), num_pages=3)
        entity = _make_file_entity("pdf-small", pdf_path, "application/pdf", "pdf")

        from airweave.platform.sync.processors.chunk_embed import ChunkEmbedProcessor

        processor = ChunkEmbedProcessor()
        runtime = _make_multimodal_runtime()

        from airweave.domains.embedders.protocols import MultimodalDenseEmbedderProtocol

        with patch(
            "airweave.platform.sync.processors.chunk_embed.text_builder"
        ) as mock_tb, patch(
            "airweave.platform.sync.processors.chunk_embed.filter_empty_representations",
            new_callable=AsyncMock,
            return_value=[entity],
        ), patch(
            "airweave.platform.sync.processors.chunk_embed.isinstance",
            side_effect=lambda obj, cls: (
                cls is MultimodalDenseEmbedderProtocol
                or type(obj).__name__ == "MagicMock" and cls.__name__ == "FileEntity"
                or builtins_isinstance(obj, cls)
            ),
        ) if False else patch(  # Skip isinstance patch, use protocol directly
            "airweave.core.config.settings",
            MagicMock(ENABLE_MEDIA_SYNC=False),
        ):
            mock_tb.build_for_batch = AsyncMock(return_value=[entity])
            entity.textual_representation = "Page 1 content."

            chunks = await processor._native_multimodal_pipeline(
                [entity], MagicMock(logger=MagicMock()), runtime
            )

        assert len(chunks) >= 1
        assert chunks[0].airweave_system_metadata.dense_embedding is not None
        runtime.dense_embedder.embed_file.assert_called()

    @pytest.mark.asyncio
    async def test_oversized_pdf_produces_multiple_chunks(self, tmp_path):
        """A 15-page PDF produces multiple 6-page chunks (separate mode)."""
        pdf_path = generate_pdf(str(tmp_path / "big.pdf"), num_pages=15)

        # Verify the PDF is actually 15 pages
        doc = fitz.open(pdf_path)
        assert len(doc) == 15
        doc.close()

        entity = _make_file_entity("pdf-big", pdf_path, "application/pdf", "pdf")

        from airweave.platform.sync.processors.chunk_embed import ChunkEmbedProcessor

        processor = ChunkEmbedProcessor()
        runtime = _make_multimodal_runtime()

        with patch(
            "airweave.core.config.settings",
            MagicMock(
                MULTIMODAL_PDF_MAX_PAGES=6,
                MULTIMODAL_PDF_OVERLAP_PAGES=1,
                MULTIMODAL_AGGREGATION="separate",
                MULTIMODAL_AGGREGATION_PDF="",
            ),
        ):
            chunks = await processor._embed_oversized_pdf(
                entity, runtime.dense_embedder, DIMS
            )

        # 15 pages / step of 5 (6-1 overlap) = ceil(15/5) = 3 chunks
        assert len(chunks) == 3
        for i, chunk in enumerate(chunks):
            assert chunk.entity_id == f"pdf-big__chunk_{i}"
            assert chunk.airweave_system_metadata.dense_embedding is not None

    @pytest.mark.asyncio
    async def test_oversized_pdf_always_produces_separate_vectors(self, tmp_path):
        """PDFs always use separate mode (API limits 1 PDF per content entry)."""
        pdf_path = generate_pdf(str(tmp_path / "big.pdf"), num_pages=15)
        entity = _make_file_entity("pdf-sep", pdf_path, "application/pdf", "pdf")

        from airweave.platform.sync.processors.chunk_embed import ChunkEmbedProcessor

        processor = ChunkEmbedProcessor()
        runtime = _make_multimodal_runtime()

        with patch(
            "airweave.core.config.settings",
            MagicMock(
                MULTIMODAL_PDF_MAX_PAGES=6,
                MULTIMODAL_PDF_OVERLAP_PAGES=1,
            ),
        ):
            chunks = await processor._embed_oversized_pdf(
                entity, runtime.dense_embedder, DIMS
            )

        # Always separate: 3 chunks from 15 pages / step of 5
        assert len(chunks) == 3
        assert runtime.dense_embedder.embed_file.call_count == 3
        for i, chunk in enumerate(chunks):
            assert chunk.entity_id == f"pdf-sep__chunk_{i}"


# ---------------------------------------------------------------------------
# E2E: Audio
# ---------------------------------------------------------------------------


class TestAudioE2E:
    """Test real WAV files through the media chunker."""

    @pytest.mark.asyncio
    async def test_short_audio_no_chunking(self, tmp_path):
        """A 10-second WAV produces 1 segment (under 75s limit)."""
        wav_path = generate_wav(str(tmp_path / "short.wav"), duration_seconds=10.0)
        assert os.path.getsize(wav_path) > 0

        from airweave.platform.chunkers.media import MediaChunker

        async with MediaChunker() as chunker:
            segments = await chunker.chunk_audio(wav_path)

        assert len(segments) == 1
        assert segments[0].file_path == wav_path
        assert segments[0].start_seconds == 0.0
        assert segments[0].end_seconds == pytest.approx(10.0, abs=0.5)

    @pytest.mark.asyncio
    async def test_long_audio_produces_overlapping_segments(self, tmp_path):
        """An 85-second WAV (over 75s limit) produces 2 overlapping segments."""
        wav_path = generate_wav(str(tmp_path / "long.wav"), duration_seconds=85.0)

        from airweave.platform.chunkers.media import MediaChunker

        async with MediaChunker() as chunker:
            segments = await chunker.chunk_audio(wav_path)

            assert len(segments) >= 2

            # Verify overlap: segment N+1 starts before segment N ends
            for i in range(1, len(segments)):
                assert segments[i].start_seconds < segments[i - 1].end_seconds

            # Verify all segments are valid audio files (before cleanup)
            for seg in segments:
                assert os.path.exists(seg.file_path)
                assert os.path.getsize(seg.file_path) > 0


# ---------------------------------------------------------------------------
# E2E: Video (requires ffmpeg)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
class TestVideoE2E:
    """Test real MP4 files through the media chunker."""

    @pytest.mark.asyncio
    async def test_short_video_no_chunking(self, tmp_path):
        """A 5-second MP4 produces 1 segment."""
        mp4_path = generate_mp4(str(tmp_path / "short.mp4"), duration_seconds=5.0)
        assert mp4_path is not None

        from airweave.platform.chunkers.media import MediaChunker

        async with MediaChunker() as chunker:
            segments = await chunker.chunk_video(mp4_path)

        assert len(segments) == 1
        assert segments[0].file_path == mp4_path
        assert segments[0].has_audio is True

    @pytest.mark.asyncio
    async def test_long_video_produces_segments(self, tmp_path):
        """An 85-second MP4 (over 75s limit) produces 2 segments."""
        mp4_path = generate_mp4(str(tmp_path / "long.mp4"), duration_seconds=85.0)
        assert mp4_path is not None

        from airweave.platform.chunkers.media import MediaChunker

        async with MediaChunker() as chunker:
            segments = await chunker.chunk_video(mp4_path)

            assert len(segments) >= 2

            for seg in segments:
                assert os.path.exists(seg.file_path)
                assert seg.mime_type == "video/mp4"


# ---------------------------------------------------------------------------
# E2E: Pipeline routing with real files
# ---------------------------------------------------------------------------


class TestPipelineRoutingE2E:
    """Verify partition logic with real files of various types."""

    def test_pdf_routes_to_native(self, tmp_path):
        pdf_path = generate_pdf(str(tmp_path / "test.pdf"), num_pages=2)
        entity = _make_file_entity("pdf-1", pdf_path, "application/pdf", "pdf")

        from airweave.platform.sync.processors.chunk_embed import ChunkEmbedProcessor
        from airweave.domains.embedders.fakes.embedder import FakeMultimodalDenseEmbedder

        processor = ChunkEmbedProcessor()
        runtime = MagicMock()
        runtime.dense_embedder = FakeMultimodalDenseEmbedder(dimensions=DIMS)

        with patch("airweave.core.config.settings", MagicMock(ENABLE_MEDIA_SYNC=False)):
            native, text = processor._partition_by_embedding_mode([entity], runtime)

        assert len(native) == 1
        assert len(text) == 0

    def test_wav_routes_to_text_when_media_disabled(self, tmp_path):
        wav_path = generate_wav(str(tmp_path / "test.wav"), duration_seconds=1.0)
        entity = _make_file_entity("wav-1", wav_path, "audio/wav", "wav")

        from airweave.platform.sync.processors.chunk_embed import ChunkEmbedProcessor
        from airweave.domains.embedders.fakes.embedder import FakeMultimodalDenseEmbedder

        processor = ChunkEmbedProcessor()
        runtime = MagicMock()
        runtime.dense_embedder = FakeMultimodalDenseEmbedder(dimensions=DIMS)

        with patch("airweave.core.config.settings", MagicMock(ENABLE_MEDIA_SYNC=False)):
            native, text = processor._partition_by_embedding_mode([entity], runtime)

        assert len(native) == 0
        assert len(text) == 1  # Gated by ENABLE_MEDIA_SYNC

    def test_wav_routes_to_native_when_media_enabled(self, tmp_path):
        wav_path = generate_wav(str(tmp_path / "test.wav"), duration_seconds=1.0)
        entity = _make_file_entity("wav-2", wav_path, "audio/wav", "wav")

        from airweave.platform.sync.processors.chunk_embed import ChunkEmbedProcessor
        from airweave.domains.embedders.fakes.embedder import FakeMultimodalDenseEmbedder

        processor = ChunkEmbedProcessor()
        runtime = MagicMock()
        runtime.dense_embedder = FakeMultimodalDenseEmbedder(dimensions=DIMS)

        with patch("airweave.core.config.settings", MagicMock(ENABLE_MEDIA_SYNC=True)):
            native, text = processor._partition_by_embedding_mode([entity], runtime)

        assert len(native) == 1
        assert len(text) == 0
