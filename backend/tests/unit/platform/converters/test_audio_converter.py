"""Unit tests for AudioConverter — all backends and paths covered."""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.platform.converters.audio_converter import AudioConverter


# ---------------------------------------------------------------------------
# Gemini backend tests
# ---------------------------------------------------------------------------


class TestGeminiBackend:
    """Tests for the default Gemini transcription backend."""

    @pytest.mark.asyncio
    async def test_transcribe_success(self, tmp_path):
        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"\x00" * 100)

        mock_response = MagicMock()
        mock_response.text = "Hello, this is a transcript."

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        converter = AudioConverter(gemini_api_key="test-key")
        with patch.object(converter, "_get_gemini_client", return_value=mock_client):
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
        with patch.object(converter, "_get_gemini_client", return_value=mock_client):
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
        with patch.object(converter, "_get_gemini_client", return_value=mock_client):
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
        with patch.object(converter, "_get_gemini_client", return_value=mock_client):
            results = await converter.convert_batch([str(audio)])

        assert results[str(audio)] == "Wav transcript"

    @pytest.mark.asyncio
    async def test_timeout_on_generate_content(self, tmp_path):
        """Gemini calls should timeout after _TRANSCRIBE_TIMEOUT."""
        audio = tmp_path / "slow.mp3"
        audio.write_bytes(b"\x00" * 100)

        async def slow_generate(*a, **kw):
            await asyncio.sleep(999)

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = slow_generate

        converter = AudioConverter(gemini_api_key="test-key")
        with patch.object(converter, "_get_gemini_client", return_value=mock_client), \
             patch("airweave.platform.converters.audio_converter._TRANSCRIBE_TIMEOUT", 0.01):
            results = await converter.convert_batch([str(audio)])

        assert results[str(audio)] is None  # Timeout → caught → None

    def test_gemini_client_cached(self):
        """_get_gemini_client should return the same client on repeated calls."""
        converter = AudioConverter(gemini_api_key="test-key")
        client1 = converter._get_gemini_client()
        client2 = converter._get_gemini_client()
        assert client1 is client2

    @pytest.mark.asyncio
    async def test_large_file_routes_to_chunked(self, tmp_path):
        """Files exceeding inline limit should be transcribed via chunked path."""
        audio = tmp_path / "big.mp3"
        # Write a file larger than 19MB
        audio.write_bytes(b"\x00" * (20 * 1024 * 1024))

        converter = AudioConverter(gemini_api_key="test-key")
        converter._config["backend"] = "gemini"

        with patch.object(
            converter, "_transcribe_chunked",
            new_callable=AsyncMock,
            return_value="chunked result",
        ) as mock_chunked:
            results = await converter.convert_batch([str(audio)])

        mock_chunked.assert_called_once()
        assert results[str(audio)] == "chunked result"

    @pytest.mark.asyncio
    async def test_uses_configured_model(self, tmp_path):
        """Should pass the configured model name to Gemini."""
        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"\x00" * 100)

        mock_response = MagicMock()
        mock_response.text = "transcript"
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        converter = AudioConverter(gemini_api_key="test-key")
        converter._config["gemini_model"] = "gemini-3-flash-preview"

        with patch.object(converter, "_get_gemini_client", return_value=mock_client):
            await converter.convert_batch([str(audio)])

        call_kwargs = mock_client.aio.models.generate_content.call_args
        assert call_kwargs.kwargs["model"] == "gemini-3-flash-preview"


# ---------------------------------------------------------------------------
# Whisper backend tests
# ---------------------------------------------------------------------------


class TestWhisperBackend:
    """Tests for the OpenAI Whisper transcription backend."""

    @pytest.mark.asyncio
    async def test_whisper_transcribe_success(self, tmp_path):
        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"\x00" * 100)

        mock_model = MagicMock()
        mock_model.transcribe.return_value = {"text": "Whisper transcript"}

        converter = AudioConverter()
        converter._config["backend"] = "whisper"

        with patch.object(converter, "_get_whisper_model", return_value=mock_model):
            results = await converter.convert_batch([str(audio)])

        assert results[str(audio)] == "Whisper transcript"
        mock_model.transcribe.assert_called_once_with(str(audio))

    @pytest.mark.asyncio
    async def test_whisper_empty_result(self, tmp_path):
        audio = tmp_path / "silence.mp3"
        audio.write_bytes(b"\x00" * 100)

        mock_model = MagicMock()
        mock_model.transcribe.return_value = {"text": ""}

        converter = AudioConverter()
        converter._config["backend"] = "whisper"

        with patch.object(converter, "_get_whisper_model", return_value=mock_model):
            results = await converter.convert_batch([str(audio)])

        assert results[str(audio)] is None

    @pytest.mark.asyncio
    async def test_whisper_model_cached(self):
        """Whisper model should be loaded once and cached."""
        mock_whisper = MagicMock()
        mock_whisper.load_model.return_value = MagicMock()

        converter = AudioConverter()
        converter._config["backend"] = "whisper"
        converter._config["whisper_model"] = "turbo"

        with patch.dict("sys.modules", {"whisper": mock_whisper}):
            model1 = converter._get_whisper_model()
            model2 = converter._get_whisper_model()

        assert model1 is model2
        assert mock_whisper.load_model.call_count == 1

    @pytest.mark.asyncio
    async def test_whisper_not_installed_raises(self):
        """Should raise RuntimeError with install instructions if whisper not installed."""
        converter = AudioConverter()
        converter._config["backend"] = "whisper"

        with patch.dict("sys.modules", {"whisper": None}):
            with pytest.raises(RuntimeError, match="openai-whisper is not installed"):
                converter._get_whisper_model()

    @pytest.mark.asyncio
    async def test_whisper_no_chunking_for_large_files(self, tmp_path):
        """Whisper backend should NOT route large files to chunked (only Gemini does)."""
        audio = tmp_path / "big.mp3"
        audio.write_bytes(b"\x00" * (25 * 1024 * 1024))

        mock_model = MagicMock()
        mock_model.transcribe.return_value = {"text": "Full file"}

        converter = AudioConverter()
        converter._config["backend"] = "whisper"

        with patch.object(converter, "_get_whisper_model", return_value=mock_model):
            results = await converter.convert_batch([str(audio)])

        # Direct transcribe, NOT chunked
        assert results[str(audio)] == "Full file"
        mock_model.transcribe.assert_called_once()


# ---------------------------------------------------------------------------
# MLX Whisper backend tests
# ---------------------------------------------------------------------------


class TestMLXWhisperBackend:
    """Tests for the MLX Whisper (Apple Silicon) backend."""

    @pytest.mark.asyncio
    async def test_mlx_whisper_success(self, tmp_path):
        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"\x00" * 100)

        mock_mlx = MagicMock()
        mock_mlx.transcribe.return_value = {"text": "MLX transcript"}

        converter = AudioConverter()
        converter._config["backend"] = "mlx_whisper"
        converter._config["whisper_model"] = "turbo"

        with patch.dict("sys.modules", {"mlx_whisper": mock_mlx}):
            results = await converter.convert_batch([str(audio)])

        assert results[str(audio)] == "MLX transcript"
        # Should map "turbo" to the MLX community repo
        mock_mlx.transcribe.assert_called_once()
        call_kwargs = mock_mlx.transcribe.call_args
        assert "mlx-community/whisper-large-v3-turbo" in str(call_kwargs)

    @pytest.mark.asyncio
    async def test_mlx_whisper_not_installed(self, tmp_path):
        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"\x00" * 100)

        converter = AudioConverter()
        converter._config["backend"] = "mlx_whisper"

        with patch.dict("sys.modules", {"mlx_whisper": None}):
            results = await converter.convert_batch([str(audio)])

        assert results[str(audio)] is None  # Error caught, returns None

    @pytest.mark.asyncio
    async def test_mlx_model_mapping(self, tmp_path):
        """Standard model names should map to MLX community repos."""
        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"\x00" * 100)

        mock_mlx = MagicMock()
        mock_mlx.transcribe.return_value = {"text": "ok"}

        converter = AudioConverter()
        converter._config["backend"] = "mlx_whisper"

        for model, expected_repo in [
            ("turbo", "mlx-community/whisper-large-v3-turbo"),
            ("large", "mlx-community/whisper-large-v3-mlx"),
            ("small", "mlx-community/whisper-small-mlx"),
        ]:
            converter._config["whisper_model"] = model
            with patch.dict("sys.modules", {"mlx_whisper": mock_mlx}):
                await converter.convert_batch([str(audio)])
                call_kwargs = mock_mlx.transcribe.call_args
                assert expected_repo in str(call_kwargs), f"Failed for {model}"


# ---------------------------------------------------------------------------
# Parakeet backend tests
# ---------------------------------------------------------------------------


class TestParakeetBackend:
    """Tests for the NVIDIA Parakeet TDT backend."""

    @pytest.mark.asyncio
    async def test_parakeet_success(self, tmp_path):
        audio = tmp_path / "test.wav"
        audio.write_bytes(b"\x00" * 100)

        mock_output = MagicMock()
        mock_output.text = "Parakeet transcript"

        mock_model = MagicMock()
        mock_model.transcribe.return_value = [mock_output]

        converter = AudioConverter()
        converter._config["backend"] = "parakeet"

        with patch.object(converter, "_get_parakeet_model", return_value=mock_model):
            results = await converter.convert_batch([str(audio)])

        assert results[str(audio)] == "Parakeet transcript"

    @pytest.mark.asyncio
    async def test_parakeet_empty_output(self, tmp_path):
        audio = tmp_path / "silence.wav"
        audio.write_bytes(b"\x00" * 100)

        mock_output = MagicMock()
        mock_output.text = ""

        mock_model = MagicMock()
        mock_model.transcribe.return_value = [mock_output]

        converter = AudioConverter()
        converter._config["backend"] = "parakeet"

        with patch.object(converter, "_get_parakeet_model", return_value=mock_model):
            results = await converter.convert_batch([str(audio)])

        assert results[str(audio)] is None

    @pytest.mark.asyncio
    async def test_parakeet_not_installed(self):
        converter = AudioConverter()
        converter._config["backend"] = "parakeet"

        with patch.dict("sys.modules", {"nemo": None, "nemo.collections": None, "nemo.collections.asr": None}):
            with pytest.raises(RuntimeError, match="nemo_toolkit"):
                converter._get_parakeet_model()


# ---------------------------------------------------------------------------
# Backend routing tests
# ---------------------------------------------------------------------------


class TestBackendRouting:
    """Tests for backend selection and routing logic."""

    @pytest.mark.asyncio
    async def test_invalid_backend_raises(self, tmp_path):
        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"\x00" * 100)

        converter = AudioConverter()
        converter._config["backend"] = "nonexistent"

        results = await converter.convert_batch([str(audio)])
        assert results[str(audio)] is None  # Error caught in convert_batch

    def test_batch_size(self):
        converter = AudioConverter(gemini_api_key="test-key")
        assert converter.BATCH_SIZE == 1


# ---------------------------------------------------------------------------
# Device resolution tests
# ---------------------------------------------------------------------------


class TestDeviceResolution:
    """Tests for automatic device detection."""

    def test_explicit_device(self):
        with patch(
            "airweave.platform.converters.audio_converter._load_transcription_config",
            return_value={"device": "cuda"},
        ):
            # Re-read from settings path
            converter = AudioConverter()
            with patch("airweave.core.config.settings") as mock_settings:
                mock_settings.MULTIMODAL_TRANSCRIPTION_DEVICE = "cuda"
                assert AudioConverter._resolve_device() == "cuda"

    def test_auto_device_no_torch(self):
        """Without torch, should default to cpu."""
        with patch("airweave.core.config.settings") as mock_settings, \
             patch.dict("sys.modules", {"torch": None}):
            mock_settings.MULTIMODAL_TRANSCRIPTION_DEVICE = "auto"
            assert AudioConverter._resolve_device() == "cpu"
