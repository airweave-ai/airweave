"""Audio-to-text converter using Gemini generate_content for transcription.

Populates textual_representation for BM25 sparse scoring, answer generation,
and reranking. Uses Gemini's multimodal generate_content (NOT embedding API)
to transcribe audio to text.

Large files are transcribed in segments via MediaChunker to stay within
Gemini's 20MB inline_data limit and avoid OOM.
"""

import os
from typing import Dict, List, Optional

import aiofiles

from airweave.core.logging import logger
from airweave.platform.converters._base import BaseTextConverter

# Gemini inline_data limit is 20MB. Stay conservative.
_MAX_INLINE_BYTES: int = 19 * 1024 * 1024  # 19 MB


class AudioConverter(BaseTextConverter):
    """Transcribe audio files to text using Gemini generate_content.

    For files under 19MB, transcribes directly via inline_data.
    For larger files, splits into segments via MediaChunker first,
    transcribes each segment, and concatenates the results.
    """

    BATCH_SIZE: int = 1

    def __init__(self, *, gemini_api_key: str | None = None) -> None:
        self._api_key = gemini_api_key

    def _get_client(self):
        """Lazily create the Gemini client."""
        from google import genai

        api_key = self._api_key
        if not api_key:
            from airweave.core.config import settings

            api_key = settings.GEMINI_API_KEY

        if not api_key:
            raise RuntimeError("Gemini API key required for audio transcription")

        return genai.Client(api_key=api_key)

    async def convert_batch(self, file_paths: List[str]) -> Dict[str, Optional[str]]:
        """Transcribe audio files to text."""
        results: Dict[str, Optional[str]] = {}

        for path in file_paths:
            name = os.path.basename(path)
            try:
                file_size = os.path.getsize(path)
                if file_size > _MAX_INLINE_BYTES:
                    transcript = await self._transcribe_chunked(path)
                else:
                    transcript = await self._transcribe(path)

                if transcript:
                    results[path] = transcript
                    logger.debug(f"{name}: transcribed via Gemini")
                else:
                    logger.warning(f"{name}: transcription returned empty")
                    results[path] = None
            except Exception as e:
                logger.warning(f"{name}: transcription failed: {e}")
                results[path] = None

        return results

    async def _transcribe(self, file_path: str) -> Optional[str]:
        """Transcribe a single audio file using Gemini generate_content."""
        from google.genai.types import Blob, Part

        ext = os.path.splitext(file_path)[1].lower()
        mime_map = {".mp3": "audio/mpeg", ".wav": "audio/wav"}
        mime_type = mime_map.get(ext, "audio/mpeg")

        async with aiofiles.open(file_path, "rb") as f:
            audio_bytes = await f.read()

        client = self._get_client()
        part = Part(inline_data=Blob(data=audio_bytes, mime_type=mime_type))

        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                "Transcribe the following audio. Return only the transcript text, "
                "no commentary or formatting.",
                part,
            ],
        )

        if response and response.text:
            return response.text.strip()
        return None

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
