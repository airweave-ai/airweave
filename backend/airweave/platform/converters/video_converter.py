"""Video-to-text converter that extracts audio and transcribes via Gemini.

Extracts the audio track from a video using ffmpeg, then delegates
to AudioConverter for transcription. Falls back to an empty string
if the video has no audio track.
"""

import asyncio
import os
import tempfile
from typing import Dict, List, Optional

from airweave.core.logging import logger
from airweave.platform.converters._base import BaseTextConverter


class VideoConverter(BaseTextConverter):
    """Extract audio from video and transcribe to text.

    Uses ffmpeg to extract the audio track, then delegates to
    AudioConverter for Gemini-based transcription. If the video
    has no audio track, returns an empty description.
    """

    BATCH_SIZE: int = 1

    def __init__(self, *, gemini_api_key: str | None = None) -> None:
        """Initialize the video converter.

        Args:
            gemini_api_key: Google Gemini API key passed to AudioConverter.
        """
        self._api_key = gemini_api_key

    async def convert_batch(self, file_paths: List[str]) -> Dict[str, Optional[str]]:
        """Extract audio from videos and transcribe.

        Args:
            file_paths: List of video file paths.

        Returns:
            Dict mapping file_path -> transcribed text (None on failure).
        """
        results: Dict[str, Optional[str]] = {}

        for path in file_paths:
            name = os.path.basename(path)
            try:
                transcript = await self._extract_and_transcribe(path)
                if transcript:
                    results[path] = transcript
                    logger.debug(f"{name}: video transcribed via audio extraction")
                else:
                    # Return a non-empty placeholder so text_builder doesn't
                    # skip this entity. The native multimodal pipeline will
                    # embed the raw video file directly.
                    results[path] = f"[Video: {name}]"
                    logger.info(f"{name}: video has no audio, using placeholder text")
            except Exception as e:
                logger.warning(f"{name}: video transcription failed: {e}")
                results[path] = None

        return results

    async def _extract_and_transcribe(self, video_path: str) -> Optional[str]:
        """Extract audio track from video and transcribe."""
        has_audio = await self._has_audio_track(video_path)
        if not has_audio:
            return ""

        # Extract audio to a temporary wav file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            audio_path = tmp.name

        try:
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vn",  # no video
                "-acodec", "pcm_s16le",
                "-ar", "16000",
                "-ac", "1",
                audio_path,
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.warning(
                    f"ffmpeg audio extraction failed: {stderr.decode(errors='replace')[:200]}"
                )
                return None

            # Transcribe the extracted audio
            from airweave.platform.converters.audio_converter import AudioConverter

            converter = AudioConverter(gemini_api_key=self._api_key)
            results = await converter.convert_batch([audio_path])
            return results.get(audio_path)

        finally:
            if os.path.exists(audio_path):
                os.unlink(audio_path)

    @staticmethod
    async def _has_audio_track(video_path: str) -> bool:
        """Check if video has an audio stream via ffprobe."""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=codec_type",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return bool(stdout.decode().strip())
