"""Unit tests for VideoConverter — ffmpeg + Gemini transcription mocked."""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.platform.converters.video_converter import VideoConverter


# ---------------------------------------------------------------------------
# convert_batch behavior
# ---------------------------------------------------------------------------


class TestConvertBatch:
    @pytest.mark.asyncio
    async def test_no_audio_track_returns_placeholder(self, tmp_path):
        """Video without audio returns a non-empty placeholder (not empty string)."""
        video = tmp_path / "silent.mp4"
        video.write_bytes(b"\x00" * 100)

        converter = VideoConverter(gemini_api_key="test-key")

        with patch.object(converter, "_has_audio_track", new_callable=AsyncMock, return_value=False):
            results = await converter.convert_batch([str(video)])

        result = results[str(video)]
        assert result is not None
        assert len(result) > 0
        assert "silent.mp4" in result

    @pytest.mark.asyncio
    async def test_transcription_failure_returns_placeholder(self, tmp_path):
        video = tmp_path / "fail.mp4"
        video.write_bytes(b"\x00" * 100)

        converter = VideoConverter(gemini_api_key="test-key")

        with patch.object(
            converter, "_extract_and_transcribe",
            new_callable=AsyncMock,
            side_effect=RuntimeError("ffmpeg crashed"),
        ):
            results = await converter.convert_batch([str(video)])

        assert results[str(video)] == f"[Video: {video.name}]"

    @pytest.mark.asyncio
    async def test_successful_transcription(self, tmp_path):
        video = tmp_path / "talk.mp4"
        video.write_bytes(b"\x00" * 100)

        converter = VideoConverter(gemini_api_key="test-key")

        with patch.object(
            converter, "_extract_and_transcribe",
            new_callable=AsyncMock,
            return_value="Hello from the video",
        ):
            results = await converter.convert_batch([str(video)])

        assert results[str(video)] == "## Audio Transcript\nHello from the video"

    @pytest.mark.asyncio
    async def test_ocr_plus_audio(self, tmp_path):
        """Both OCR and audio produce combined output."""
        video = tmp_path / "slides.mp4"
        video.write_bytes(b"\x00" * 100)

        converter = VideoConverter(gemini_api_key="test-key")

        with patch.object(
            converter, "_ocr_keyframes",
            new_callable=AsyncMock,
            return_value="Slide text here",
        ), patch.object(
            converter, "_extract_and_transcribe",
            new_callable=AsyncMock,
            return_value="Speaker narration",
        ):
            results = await converter.convert_batch([str(video)])

        result = results[str(video)]
        assert "## Visual Content (OCR)" in result
        assert "Slide text here" in result
        assert "## Audio Transcript" in result
        assert "Speaker narration" in result

    @pytest.mark.asyncio
    async def test_empty_transcription_returns_placeholder(self, tmp_path):
        """Both OCR and transcription fail → placeholder."""
        video = tmp_path / "blank.mp4"
        video.write_bytes(b"\x00" * 100)

        converter = VideoConverter(gemini_api_key="test-key")

        with patch.object(
            converter, "_ocr_keyframes",
            new_callable=AsyncMock,
            return_value=None,
        ), patch.object(
            converter, "_extract_and_transcribe",
            new_callable=AsyncMock,
            return_value=None,
        ):
            results = await converter.convert_batch([str(video)])

        assert results[str(video)] == "[Video: blank.mp4]"

    def test_batch_size(self):
        converter = VideoConverter(gemini_api_key="test-key")
        assert converter.BATCH_SIZE == 1


# ---------------------------------------------------------------------------
# Client caching
# ---------------------------------------------------------------------------


class TestClientCaching:
    def test_client_cached_across_calls(self):
        """_get_client should cache the Gemini client."""
        converter = VideoConverter(gemini_api_key="test-key")
        client1 = converter._get_client()
        client2 = converter._get_client()
        assert client1 is client2

    def test_no_api_key_returns_none(self):
        converter = VideoConverter(gemini_api_key=None)
        # Clear any env vars that might provide a key
        with patch.dict("os.environ", {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}, clear=False), \
             patch("airweave.core.config.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = None
            result = converter._get_client()
        assert result is None


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


class TestDeduplication:
    def test_empty_input(self):
        assert VideoConverter._deduplicate_texts([]) == []

    def test_no_duplicates(self):
        texts = ["hello", "world", "different text"]
        result = VideoConverter._deduplicate_texts(texts)
        assert result == texts

    def test_consecutive_duplicates_removed(self):
        texts = ["Slide 1: Hello", "Slide 1: Hello", "Slide 2: World"]
        result = VideoConverter._deduplicate_texts(texts)
        assert len(result) == 2
        assert result[0] == "Slide 1: Hello"
        assert result[1] == "Slide 2: World"

    def test_similar_above_threshold_removed(self):
        # >80% character overlap should be deduplicated
        texts = ["The quick brown fox jumps", "The quick brown fox jump!", "Completely different"]
        result = VideoConverter._deduplicate_texts(texts)
        assert len(result) == 2  # Second too similar to first

    def test_empty_strings_skipped(self):
        texts = ["hello", "", "", "world"]
        result = VideoConverter._deduplicate_texts(texts)
        assert result == ["hello", "world"]


# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------


class TestModelConfig:
    def test_default_model(self):
        model = VideoConverter._get_transcription_model()
        assert "gemini" in model  # Should be a Gemini model

    def test_configured_model(self):
        with patch("airweave.core.config.settings") as mock_settings:
            mock_settings.MULTIMODAL_TRANSCRIPTION_MODEL = "gemini-3-flash-preview"
            model = VideoConverter._get_transcription_model()
        assert model == "gemini-3-flash-preview"


# ---------------------------------------------------------------------------
# OCR keyframe extraction (ffmpeg filter)
# ---------------------------------------------------------------------------


class TestKeyframeExtraction:
    @pytest.mark.asyncio
    async def test_ffmpeg_includes_first_frame(self, tmp_path):
        """The ffmpeg filter should include eq(n,0) for first frame."""
        video = tmp_path / "static.mp4"
        video.write_bytes(b"\x00" * 100)

        converter = VideoConverter(gemini_api_key="test-key")
        captured_cmd = []

        async def mock_subprocess(*args, **kwargs):
            captured_cmd.extend(args)
            proc = MagicMock()
            proc.returncode = 1  # Fail to short-circuit
            proc.communicate = AsyncMock(return_value=(b"", b"fail"))
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            result = await converter._ocr_keyframes(str(video))

        # The ffmpeg command should contain eq(n,0) in the filter
        cmd_str = " ".join(str(x) for x in captured_cmd)
        assert "eq(n" in cmd_str  # eq(n\,0) in the filter

    @pytest.mark.asyncio
    async def test_no_frames_returns_none(self, tmp_path):
        """If ffmpeg extracts zero frames, returns None."""
        video = tmp_path / "black.mp4"
        video.write_bytes(b"\x00" * 100)

        converter = VideoConverter(gemini_api_key="test-key")

        async def mock_subprocess(*args, **kwargs):
            proc = MagicMock()
            proc.returncode = 0  # Success but no frames
            proc.communicate = AsyncMock(return_value=(b"", b""))
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            result = await converter._ocr_keyframes(str(video))

        assert result is None

    @pytest.mark.asyncio
    async def test_gemini_ocr_timeout(self, tmp_path):
        """OCR frame calls should timeout after _OCR_TIMEOUT."""
        frame = tmp_path / "frame.jpg"
        frame.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)  # Fake JPEG

        converter = VideoConverter(gemini_api_key="test-key")

        async def slow_generate(*a, **kw):
            await asyncio.sleep(999)

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = slow_generate

        with patch.object(converter, "_get_client", return_value=mock_client), \
             patch("airweave.platform.converters.video_converter._OCR_TIMEOUT", 0.01):
            result = await converter._gemini_ocr_frame(str(frame))

        assert result is None  # Timeout caught
