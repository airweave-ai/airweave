"""Unit tests for VideoConverter — ffmpeg + Gemini transcription mocked."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.platform.converters.video_converter import VideoConverter


class TestVideoConverter:
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
        assert len(result) > 0  # Must be truthy so text_builder doesn't skip
        assert "silent.mp4" in result

    @pytest.mark.asyncio
    async def test_transcription_failure_returns_none(self, tmp_path):
        video = tmp_path / "fail.mp4"
        video.write_bytes(b"\x00" * 100)

        converter = VideoConverter(gemini_api_key="test-key")

        with patch.object(
            converter, "_extract_and_transcribe",
            new_callable=AsyncMock,
            side_effect=RuntimeError("ffmpeg crashed"),
        ):
            results = await converter.convert_batch([str(video)])

        # convert_batch returns a placeholder on failure, not None
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

        # _convert_video wraps audio transcript in a markdown section header
        assert results[str(video)] == "## Audio Transcript\nHello from the video"

    def test_batch_size(self):
        converter = VideoConverter(gemini_api_key="test-key")
        assert converter.BATCH_SIZE == 1
