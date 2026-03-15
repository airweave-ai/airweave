"""Unit tests for AudioConverter — Gemini transcription mocked."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.platform.converters.audio_converter import AudioConverter


class TestAudioConverter:
    @pytest.mark.asyncio
    async def test_transcribe_success(self, tmp_path):
        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"\x00" * 100)

        mock_response = MagicMock()
        mock_response.text = "Hello, this is a transcript."

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        converter = AudioConverter(gemini_api_key="test-key")
        with patch.object(converter, "_get_client", return_value=mock_client):
            results = await converter.convert_batch([str(audio)])

        assert results[str(audio)] == "Hello, this is a transcript."

    @pytest.mark.asyncio
    async def test_transcribe_empty_response(self, tmp_path):
        audio = tmp_path / "empty.mp3"
        audio.write_bytes(b"\x00" * 100)

        mock_response = MagicMock()
        mock_response.text = ""

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        converter = AudioConverter(gemini_api_key="test-key")
        with patch.object(converter, "_get_client", return_value=mock_client):
            results = await converter.convert_batch([str(audio)])

        assert results[str(audio)] is None

    @pytest.mark.asyncio
    async def test_transcribe_api_failure(self, tmp_path):
        audio = tmp_path / "fail.mp3"
        audio.write_bytes(b"\x00" * 100)

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=RuntimeError("API failure")
        )

        converter = AudioConverter(gemini_api_key="test-key")
        with patch.object(converter, "_get_client", return_value=mock_client):
            results = await converter.convert_batch([str(audio)])

        assert results[str(audio)] is None

    @pytest.mark.asyncio
    async def test_wav_mime_type(self, tmp_path):
        audio = tmp_path / "test.wav"
        audio.write_bytes(b"\x00" * 100)

        mock_response = MagicMock()
        mock_response.text = "Wav transcript"

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        converter = AudioConverter(gemini_api_key="test-key")
        with patch.object(converter, "_get_client", return_value=mock_client):
            results = await converter.convert_batch([str(audio)])

        assert results[str(audio)] == "Wav transcript"

    def test_batch_size(self):
        converter = AudioConverter(gemini_api_key="test-key")
        assert converter.BATCH_SIZE == 1
