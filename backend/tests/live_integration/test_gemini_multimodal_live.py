"""Live integration tests for Gemini Embedding 2 multimodal pipeline.

These tests call the REAL Gemini API with REAL generated media files.
They verify actual embedding dimensions, normalization, and vector quality.

Requirements:
    - GEMINI_API_KEY environment variable set
    - ffmpeg installed (for video tests)
    - Network access to generativelanguage.googleapis.com

Run:
    pytest tests/live_integration/test_gemini_multimodal_live.py -v -m live_integration
"""

import math
import os
import shutil
import struct
import wave

import fitz  # PyMuPDF
import pytest

_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
_MODEL = "gemini-embedding-2-preview"
_DIMS = 768  # Use a moderate Matryoshka dim for testing


pytestmark = [
    pytest.mark.live_integration,
    pytest.mark.skipif(not _API_KEY, reason="GEMINI_API_KEY not set"),
]


# ---------------------------------------------------------------------------
# Fixture generators (same as E2E but real files)
# ---------------------------------------------------------------------------


def generate_pdf(path: str, num_pages: int) -> str:
    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page(width=612, height=792)
        page.insert_text(
            (72, 72),
            f"Page {i + 1}: The quick brown fox jumps over the lazy dog. "
            f"This is test content for Gemini Embedding 2 multimodal verification.",
            fontsize=11,
        )
    doc.save(path)
    doc.close()
    return path


def generate_wav(path: str, duration_seconds: float, frequency: int = 440) -> str:
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
            "-shortest", path,
        ],
        capture_output=True, timeout=30,
    )
    return path if os.path.exists(path) else None


def _l2_norm(vector: list[float]) -> float:
    return math.sqrt(sum(x * x for x in vector))


# ---------------------------------------------------------------------------
# Live: Text embedding (baseline)
# ---------------------------------------------------------------------------


class TestLiveTextEmbedding:
    """Verify the embedder works at all before testing multimodal."""

    @pytest.mark.asyncio
    async def test_single_text_embedding(self):
        from airweave.domains.embedders.dense.gemini import GeminiDenseEmbedder

        embedder = GeminiDenseEmbedder(api_key=_API_KEY, model=_MODEL, dimensions=_DIMS)
        try:
            result = await embedder.embed("The quick brown fox jumps over the lazy dog.")

            assert len(result.vector) == _DIMS
            assert all(isinstance(v, float) for v in result.vector)
            # Should be approximately L2-normalized (Matryoshka dims < 3072)
            norm = _l2_norm(result.vector)
            assert abs(norm - 1.0) < 0.01, f"Expected unit norm, got {norm}"
        finally:
            await embedder.close()


# ---------------------------------------------------------------------------
# Live: PDF embedding
# ---------------------------------------------------------------------------


class TestLivePdfEmbedding:
    @pytest.mark.asyncio
    async def test_embed_small_pdf(self, tmp_path):
        """Embed a real 3-page PDF through the Gemini API."""
        pdf_path = generate_pdf(str(tmp_path / "test.pdf"), num_pages=3)

        from airweave.domains.embedders.dense.gemini import GeminiDenseEmbedder

        embedder = GeminiDenseEmbedder(api_key=_API_KEY, model=_MODEL, dimensions=_DIMS)
        try:
            result = await embedder.embed_file(pdf_path, "application/pdf")

            assert len(result.vector) == _DIMS
            norm = _l2_norm(result.vector)
            assert abs(norm - 1.0) < 0.01, f"PDF embed norm: {norm}"

            # Verify it's not a zero vector
            assert any(abs(v) > 1e-6 for v in result.vector)
        finally:
            await embedder.close()

    @pytest.mark.asyncio
    async def test_oversized_pdf_rejected(self, tmp_path):
        """A 10-page PDF should be rejected (exceeds 6-page limit)."""
        pdf_path = generate_pdf(str(tmp_path / "big.pdf"), num_pages=10)

        from airweave.domains.embedders.dense.gemini import GeminiDenseEmbedder
        from airweave.domains.embedders.exceptions import EmbedderInputError

        embedder = GeminiDenseEmbedder(api_key=_API_KEY, model=_MODEL, dimensions=_DIMS)
        try:
            with pytest.raises(EmbedderInputError, match="pages"):
                await embedder.embed_file(pdf_path, "application/pdf")
        finally:
            await embedder.close()

    @pytest.mark.asyncio
    async def test_two_separate_pdf_chunks_produce_different_vectors(self, tmp_path):
        """Two different 6-page PDFs should produce distinct embedding vectors."""
        pdf1 = generate_pdf(str(tmp_path / "part1.pdf"), num_pages=6)
        # Create a second PDF with different content
        doc2 = fitz.open()
        for i in range(6):
            page = doc2.new_page(width=612, height=792)
            page.insert_text(
                (72, 72),
                f"Page {i+1}: Quantum mechanics describes the behavior "
                f"of subatomic particles at very small scales.",
                fontsize=11,
            )
        doc2.save(str(tmp_path / "part2.pdf"))
        doc2.close()
        pdf2 = str(tmp_path / "part2.pdf")

        from airweave.domains.embedders.dense.gemini import GeminiDenseEmbedder

        embedder = GeminiDenseEmbedder(api_key=_API_KEY, model=_MODEL, dimensions=_DIMS)
        try:
            vec1 = await embedder.embed_file(pdf1, "application/pdf")
            vec2 = await embedder.embed_file(pdf2, "application/pdf")

            assert len(vec1.vector) == _DIMS
            assert len(vec2.vector) == _DIMS

            # Different content should produce different vectors
            diff = sum(abs(a - b) for a, b in zip(vec1.vector, vec2.vector))
            assert diff > 0.1, f"PDFs with different content should differ, L1 diff: {diff}"
        finally:
            await embedder.close()

    @pytest.mark.asyncio
    async def test_pdf_vector_differs_from_text_vector(self, tmp_path):
        """Native PDF embedding should produce a different vector than text extraction."""
        pdf_path = generate_pdf(str(tmp_path / "test.pdf"), num_pages=1)

        from airweave.domains.embedders.dense.gemini import GeminiDenseEmbedder

        embedder = GeminiDenseEmbedder(api_key=_API_KEY, model=_MODEL, dimensions=_DIMS)
        try:
            pdf_vec = await embedder.embed_file(pdf_path, "application/pdf")
            text_vec = await embedder.embed(
                "Page 1: The quick brown fox jumps over the lazy dog. "
                "This is test content for Gemini Embedding 2 multimodal verification."
            )

            # Vectors should be related but not identical
            cosine_sim = sum(
                a * b for a, b in zip(pdf_vec.vector, text_vec.vector)
            )
            # High similarity (same content) but not 1.0 (different modality)
            assert 0.3 < cosine_sim < 1.0, f"Cosine similarity: {cosine_sim}"
        finally:
            await embedder.close()


# ---------------------------------------------------------------------------
# Live: Audio embedding
# ---------------------------------------------------------------------------


class TestLiveAudioEmbedding:
    @pytest.mark.asyncio
    async def test_embed_wav_file(self, tmp_path):
        """Embed a real WAV file (10s sine tone) through the Gemini API."""
        wav_path = generate_wav(str(tmp_path / "tone.wav"), duration_seconds=10.0)

        from airweave.domains.embedders.dense.gemini import GeminiDenseEmbedder

        embedder = GeminiDenseEmbedder(api_key=_API_KEY, model=_MODEL, dimensions=_DIMS)
        try:
            result = await embedder.embed_file(wav_path, "audio/wav")

            assert len(result.vector) == _DIMS
            norm = _l2_norm(result.vector)
            assert abs(norm - 1.0) < 0.01, f"Audio embed norm: {norm}"
            assert any(abs(v) > 1e-6 for v in result.vector)
        finally:
            await embedder.close()

    @pytest.mark.asyncio
    async def test_different_frequencies_produce_different_vectors(self, tmp_path):
        """Two audio files with different frequencies should have different embeddings."""
        wav_low = generate_wav(str(tmp_path / "low.wav"), duration_seconds=5.0, frequency=220)
        wav_high = generate_wav(str(tmp_path / "high.wav"), duration_seconds=5.0, frequency=880)

        from airweave.domains.embedders.dense.gemini import GeminiDenseEmbedder

        embedder = GeminiDenseEmbedder(api_key=_API_KEY, model=_MODEL, dimensions=_DIMS)
        try:
            low_vec = await embedder.embed_file(wav_low, "audio/wav")
            high_vec = await embedder.embed_file(wav_high, "audio/wav")

            # Vectors should not be identical
            diff = sum(abs(a - b) for a, b in zip(low_vec.vector, high_vec.vector))
            assert diff > 0.01, "Different audio should produce different vectors"
        finally:
            await embedder.close()


# ---------------------------------------------------------------------------
# Live: Video embedding (requires ffmpeg)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
class TestLiveVideoEmbedding:
    @pytest.mark.asyncio
    async def test_embed_mp4_file(self, tmp_path):
        """Embed a real MP4 (5s test pattern + tone) through the Gemini API."""
        mp4_path = generate_mp4(str(tmp_path / "test.mp4"), duration_seconds=5.0)
        assert mp4_path is not None

        from airweave.domains.embedders.dense.gemini import GeminiDenseEmbedder

        embedder = GeminiDenseEmbedder(api_key=_API_KEY, model=_MODEL, dimensions=_DIMS)
        try:
            result = await embedder.embed_file(mp4_path, "video/mp4")

            assert len(result.vector) == _DIMS
            norm = _l2_norm(result.vector)
            assert abs(norm - 1.0) < 0.01, f"Video embed norm: {norm}"
            assert any(abs(v) > 1e-6 for v in result.vector)
        finally:
            await embedder.close()


# ---------------------------------------------------------------------------
# Live: Cross-modal similarity
# ---------------------------------------------------------------------------


class TestLiveCrossModalSimilarity:
    @pytest.mark.asyncio
    async def test_text_query_retrieves_related_pdf(self, tmp_path):
        """A text query about the PDF content should have high cosine sim to the PDF embedding."""
        pdf_path = generate_pdf(str(tmp_path / "fox.pdf"), num_pages=1)

        from airweave.domains.embedders.dense.gemini import GeminiDenseEmbedder
        from airweave.domains.embedders.protocols import EmbeddingPurpose

        embedder = GeminiDenseEmbedder(api_key=_API_KEY, model=_MODEL, dimensions=_DIMS)
        try:
            doc_vec = await embedder.embed_file(
                pdf_path, "application/pdf", purpose=EmbeddingPurpose.DOCUMENT
            )
            query_vec = await embedder.embed(
                "quick brown fox lazy dog", purpose=EmbeddingPurpose.QUERY
            )
            unrelated_vec = await embedder.embed(
                "quantum mechanics wave function collapse",
                purpose=EmbeddingPurpose.QUERY,
            )

            related_sim = sum(
                a * b for a, b in zip(doc_vec.vector, query_vec.vector)
            )
            unrelated_sim = sum(
                a * b for a, b in zip(doc_vec.vector, unrelated_vec.vector)
            )

            # Related query should score higher than unrelated
            assert related_sim > unrelated_sim, (
                f"Related sim ({related_sim:.4f}) should be > "
                f"unrelated sim ({unrelated_sim:.4f})"
            )
        finally:
            await embedder.close()
