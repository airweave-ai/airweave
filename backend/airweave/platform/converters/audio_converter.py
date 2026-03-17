"""Audio-to-text converter with pluggable transcription backends.

Populates textual_representation for BM25 sparse scoring, answer generation,
and reranking.

Supported backends (configured via MULTIMODAL_TRANSCRIPTION_BACKEND):
- "gemini": Google Gemini generate_content API (cloud, requires API key)
- "whisper": OpenAI Whisper (local, CPU/CUDA/MPS, pip install openai-whisper)
- "mlx_whisper": MLX Whisper for Apple Silicon (local, pip install mlx-whisper)
- "parakeet": NVIDIA Parakeet TDT v3 (local, CUDA, pip install nemo_toolkit[asr])

Large files are transcribed in segments via MediaChunker to stay within
per-backend limits and avoid OOM.
"""

import asyncio
import os
from typing import Dict, List, Optional

import aiofiles

from airweave.core.logging import logger
from airweave.platform.converters._base import BaseTextConverter

# Timeout for cloud API calls (seconds)
_TRANSCRIBE_TIMEOUT: float = 120.0


def _load_transcription_config() -> dict:
    """Load all transcription settings, falling back to defaults."""
    try:
        from airweave.core.config import settings

        return {
            "backend": getattr(settings, "MULTIMODAL_TRANSCRIPTION_BACKEND", "gemini"),
            "gemini_model": getattr(settings, "MULTIMODAL_TRANSCRIPTION_MODEL", "gemini-3-flash-preview"),
            "whisper_model": getattr(settings, "MULTIMODAL_WHISPER_MODEL", "turbo"),
            "parakeet_model": getattr(settings, "MULTIMODAL_PARAKEET_MODEL", "nvidia/parakeet-tdt-0.6b-v3"),
            "device": getattr(settings, "MULTIMODAL_TRANSCRIPTION_DEVICE", "auto"),
            "max_file_mb": getattr(settings, "MULTIMODAL_MAX_FILE_SIZE_MB", 20),
        }
    except Exception:
        return {
            "backend": "gemini",
            "gemini_model": "gemini-3-flash-preview",
            "whisper_model": "turbo",
            "parakeet_model": "nvidia/parakeet-tdt-0.6b-v3",
            "device": "auto",
            "max_file_mb": 20,
        }


class AudioConverter(BaseTextConverter):
    """Transcribe audio files to text using a configurable backend.

    Backend is selected via MULTIMODAL_TRANSCRIPTION_BACKEND setting.
    For files exceeding the inline limit (Gemini) or very long duration
    (local models), splits into segments via MediaChunker first.
    """

    BATCH_SIZE: int = 1

    def __init__(self, *, gemini_api_key: str | None = None) -> None:
        self._api_key = gemini_api_key
        self._gemini_client = None
        self._whisper_model = None
        self._parakeet_model = None
        self._config = _load_transcription_config()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def convert_batch(self, file_paths: List[str]) -> Dict[str, Optional[str]]:
        """Transcribe audio files to text."""
        results: Dict[str, Optional[str]] = {}
        backend = self._config["backend"]
        max_bytes = (self._config["max_file_mb"] - 1) * 1024 * 1024

        for path in file_paths:
            name = os.path.basename(path)
            try:
                file_size = os.path.getsize(path)

                # Gemini has inline_data size limit; local backends don't
                if backend == "gemini" and file_size > max_bytes:
                    transcript = await self._transcribe_chunked(path)
                else:
                    transcript = await self._transcribe(path)

                if transcript:
                    results[path] = transcript
                    logger.debug(f"{name}: transcribed via {backend}")
                else:
                    logger.warning(f"{name}: transcription returned empty")
                    results[path] = None
            except Exception as e:
                logger.warning(f"{name}: transcription failed ({backend}): {e}")
                results[path] = None

        return results

    # ------------------------------------------------------------------
    # Dispatcher
    # ------------------------------------------------------------------

    async def _transcribe(self, file_path: str) -> Optional[str]:
        """Route to the configured backend."""
        backend = self._config["backend"]
        if backend == "gemini":
            return await self._transcribe_gemini(file_path)
        elif backend == "whisper":
            return await self._transcribe_whisper(file_path)
        elif backend == "mlx_whisper":
            return await self._transcribe_mlx_whisper(file_path)
        elif backend == "parakeet":
            return await self._transcribe_parakeet(file_path)
        else:
            raise ValueError(
                f"Unknown transcription backend: {backend}. "
                f"Expected: gemini, whisper, mlx_whisper, parakeet"
            )

    async def _transcribe_chunked(self, file_path: str) -> Optional[str]:
        """Transcribe a large audio file by splitting into segments first."""
        from airweave.platform.chunkers.media import MediaChunker

        async with MediaChunker() as chunker:
            segments = await chunker.chunk_audio(file_path)

            transcripts: list[str] = []
            for seg in segments:
                text = await self._transcribe(seg.file_path)
                if text:
                    transcripts.append(text)

        if not transcripts:
            return None
        return "\n\n".join(transcripts)

    # ------------------------------------------------------------------
    # Backend: Gemini (cloud API)
    # ------------------------------------------------------------------

    def _get_gemini_client(self):
        """Lazily create and cache the Gemini client."""
        if self._gemini_client is not None:
            return self._gemini_client

        from google import genai

        api_key = self._api_key
        if not api_key:
            from airweave.core.config import settings

            api_key = settings.GEMINI_API_KEY

        if not api_key:
            raise RuntimeError("Gemini API key required for audio transcription")

        self._gemini_client = genai.Client(api_key=api_key)
        return self._gemini_client

    async def _transcribe_gemini(self, file_path: str) -> Optional[str]:
        """Transcribe via Gemini generate_content API."""
        from google.genai.types import Blob, Part

        ext = os.path.splitext(file_path)[1].lower()
        mime_map = {".mp3": "audio/mpeg", ".wav": "audio/wav"}
        mime_type = mime_map.get(ext, "audio/mpeg")

        async with aiofiles.open(file_path, "rb") as f:
            audio_bytes = await f.read()

        client = self._get_gemini_client()
        part = Part(inline_data=Blob(data=audio_bytes, mime_type=mime_type))
        model = self._config["gemini_model"]

        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=model,
                contents=[
                    "Transcribe the following audio. Return only the transcript text, "
                    "no commentary or formatting.",
                    part,
                ],
            ),
            timeout=_TRANSCRIBE_TIMEOUT,
        )

        if response and response.text:
            return response.text.strip()
        return None

    # ------------------------------------------------------------------
    # Backend: OpenAI Whisper (local, CPU/CUDA)
    # ------------------------------------------------------------------

    def _get_whisper_model(self):
        """Lazily load the Whisper model."""
        if self._whisper_model is not None:
            return self._whisper_model

        try:
            import whisper
        except ImportError:
            raise RuntimeError(
                "openai-whisper is not installed. "
                "Install with: pip install openai-whisper"
            )

        model_name = self._config["whisper_model"]
        device = self._resolve_device()
        logger.info(f"Loading Whisper model '{model_name}' on {device}")
        self._whisper_model = whisper.load_model(model_name, device=device)
        return self._whisper_model

    async def _transcribe_whisper(self, file_path: str) -> Optional[str]:
        """Transcribe via OpenAI Whisper (local)."""
        model = self._get_whisper_model()
        result = await asyncio.to_thread(model.transcribe, file_path)
        text = result.get("text", "")
        return text.strip() if text else None

    # ------------------------------------------------------------------
    # Backend: MLX Whisper (Apple Silicon)
    # ------------------------------------------------------------------

    async def _transcribe_mlx_whisper(self, file_path: str) -> Optional[str]:
        """Transcribe via MLX Whisper (Apple Silicon, local)."""
        try:
            import mlx_whisper
        except ImportError:
            raise RuntimeError(
                "mlx-whisper is not installed. "
                "Install with: pip install mlx-whisper"
            )

        model_name = self._config["whisper_model"]
        # Map standard model names to MLX community repos
        mlx_model_map = {
            "turbo": "mlx-community/whisper-large-v3-turbo",
            "large": "mlx-community/whisper-large-v3-mlx",
            "medium": "mlx-community/whisper-medium-mlx",
            "small": "mlx-community/whisper-small-mlx",
            "base": "mlx-community/whisper-base-mlx",
            "tiny": "mlx-community/whisper-tiny-mlx",
        }
        repo = mlx_model_map.get(model_name, model_name)

        result = await asyncio.to_thread(
            mlx_whisper.transcribe, file_path, path_or_hf_repo=repo
        )
        text = result.get("text", "")
        return text.strip() if text else None

    # ------------------------------------------------------------------
    # Backend: NVIDIA Parakeet (local, CUDA)
    # ------------------------------------------------------------------

    def _get_parakeet_model(self):
        """Lazily load the Parakeet ASR model."""
        if self._parakeet_model is not None:
            return self._parakeet_model

        try:
            import nemo.collections.asr as nemo_asr
        except ImportError:
            raise RuntimeError(
                "nemo_toolkit[asr] is not installed. "
                "Install with: pip install nemo_toolkit[asr]"
            )

        model_name = self._config["parakeet_model"]
        logger.info(f"Loading Parakeet model '{model_name}'")
        self._parakeet_model = nemo_asr.models.ASRModel.from_pretrained(
            model_name=model_name
        )
        return self._parakeet_model

    async def _transcribe_parakeet(self, file_path: str) -> Optional[str]:
        """Transcribe via NVIDIA Parakeet TDT (local, CUDA)."""
        model = self._get_parakeet_model()
        output = await asyncio.to_thread(model.transcribe, [file_path])
        if output and len(output) > 0:
            text = output[0].text if hasattr(output[0], "text") else str(output[0])
            return text.strip() if text else None
        return None

    # ------------------------------------------------------------------
    # Device resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_device() -> str:
        """Resolve 'auto' device to best available: CUDA > MPS > CPU."""
        try:
            from airweave.core.config import settings

            device = getattr(settings, "MULTIMODAL_TRANSCRIPTION_DEVICE", "auto")
        except Exception:
            device = "auto"

        if device != "auto":
            return device

        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "cpu"  # Whisper has limited MPS support, use CPU
        except ImportError:
            pass

        return "cpu"
