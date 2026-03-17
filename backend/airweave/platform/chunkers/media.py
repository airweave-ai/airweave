"""Media chunker for audio and video files.

Splits audio/video into segments that fit within Gemini Embedding 2's
duration and file size limits. Uses ffprobe for duration detection and
ffmpeg for stream-copy splitting (no decode into RAM). Falls back to
pydub only when ffmpeg is unavailable. Temp directories are cleaned up
via the async context manager after embedding completes.
"""

import asyncio
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Defaults — overridden by settings when available
AUDIO_MAX_SECONDS: int = 75
VIDEO_AUDIO_MAX_SECONDS: int = 75
VIDEO_NOAUDIO_MAX_SECONDS: int = 115
OVERLAP_SECONDS: int = 5


def _load_media_config() -> tuple[int, int, int, int]:
    """Load media chunking config from settings, falling back to defaults."""
    try:
        from airweave.core.config import settings

        return (
            settings.MULTIMODAL_AUDIO_MAX_SECONDS,
            settings.MULTIMODAL_VIDEO_AUDIO_MAX_SECONDS,
            settings.MULTIMODAL_VIDEO_NOAUDIO_MAX_SECONDS,
            settings.MULTIMODAL_MEDIA_OVERLAP_SECONDS,
        )
    except Exception:
        return (
            AUDIO_MAX_SECONDS,
            VIDEO_AUDIO_MAX_SECONDS,
            VIDEO_NOAUDIO_MAX_SECONDS,
            OVERLAP_SECONDS,
        )


def _get_max_single_file_bytes() -> int:
    """Centralized file size limit from settings, fallback to 19MB.

    Used by both audio and video chunkers to stay under Gemini's 20MB
    inline_data limit. Reads MULTIMODAL_MAX_FILE_SIZE_MB from settings
    and applies a 1MB safety margin.
    """
    try:
        from airweave.core.config import settings

        return (settings.MULTIMODAL_MAX_FILE_SIZE_MB - 1) * 1024 * 1024
    except Exception:
        return 19 * 1024 * 1024


@dataclass
class MediaSegment:
    """A chunk of a media file within Gemini's embedding duration limits."""

    file_path: str
    start_seconds: float
    end_seconds: float
    has_audio: bool
    mime_type: str


class MediaChunker:
    """Splits audio/video files into embeddable segments.

    Use as a context manager to ensure temp directories are cleaned up:

        async with MediaChunker() as chunker:
            segments = await chunker.chunk_audio(path)
            # ... embed segments ...
        # temp dirs cleaned up here
    """

    def __init__(self, temp_dir: str | None = None) -> None:
        self._temp_dir = temp_dir
        self._created_dirs: list[str] = []

    async def __aenter__(self) -> "MediaChunker":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        self.cleanup()

    def cleanup(self) -> None:
        """Remove all temp directories created by this chunker."""
        for d in self._created_dirs:
            try:
                shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass
        self._created_dirs.clear()

    def _get_temp_dir(self) -> str:
        if self._temp_dir:
            os.makedirs(self._temp_dir, exist_ok=True)
            return self._temp_dir
        d = tempfile.mkdtemp(prefix="airweave_media_")
        self._created_dirs.append(d)
        return d

    async def chunk_audio(self, file_path: str) -> list[MediaSegment]:
        """Split an audio file into segments using ffmpeg.

        Uses ffprobe for duration detection and ffmpeg stream-copy for splitting.
        Never decodes the full file into memory (avoids OOM on large files).
        A file is returned as-is only if BOTH duration <= limit AND size <= 19MB.
        Falls back to pydub only if ffmpeg is unavailable.

        Args:
            file_path: Path to the audio file (mp3, wav).

        Returns:
            List of MediaSegment objects, one per chunk.
        """
        audio_max, _, _, overlap = _load_media_config()
        ext = os.path.splitext(file_path)[1] or ".mp3"
        mime = "audio/mpeg" if ext == ".mp3" else "audio/wav"

        if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
            raise RuntimeError(
                "ffmpeg and ffprobe are both required for audio chunking "
                "but not found on PATH"
            )

        duration_seconds = await self._probe_duration(file_path)

        # Return as single segment only if BOTH duration and file size are safe.
        # A short but large file (e.g., 40s uncompressed WAV at 23MB) must still
        # be split because Gemini rejects inline_data > 20MB.
        max_file_bytes = _get_max_single_file_bytes()
        file_size = os.path.getsize(file_path)

        if duration_seconds <= audio_max and file_size <= max_file_bytes:
            return [
                MediaSegment(
                    file_path=file_path,
                    start_seconds=0.0,
                    end_seconds=duration_seconds,
                    has_audio=True,
                    mime_type=mime,
                )
            ]

        # If file is oversized but short, reduce segment duration to fit
        # within the size limit. Calculate from bitrate.
        if file_size > max_file_bytes and duration_seconds > 0:
            bytes_per_second = file_size / duration_seconds
            # 5% safety margin for container/header overhead (e.g., WAV headers)
            size_limited_max = (max_file_bytes * 0.95) / bytes_per_second
            # Use the smaller of duration limit and size limit
            audio_max = min(audio_max, size_limited_max)
            # Ensure at least 1 second segments
            audio_max = max(1.0, audio_max)

        temp_dir = self._get_temp_dir()
        segments: list[MediaSegment] = []
        step = max(1, audio_max - overlap)

        start = 0.0
        idx = 0

        while start < duration_seconds:
            seg_duration = min(audio_max, duration_seconds - start)
            segment_path = os.path.join(temp_dir, f"audio_seg_{idx}{ext}")

            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start),
                "-i", file_path,
                "-t", str(seg_duration),
                "-c", "copy",
                segment_path,
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.warning(
                    f"ffmpeg audio segment {idx} failed (rc={proc.returncode}): "
                    f"{stderr.decode(errors='replace')[:200]}. "
                    f"Returning {len(segments)} partial segments."
                )
                break

            segments.append(
                MediaSegment(
                    file_path=segment_path,
                    start_seconds=start,
                    end_seconds=start + seg_duration,
                    has_audio=True,
                    mime_type=mime,
                )
            )

            start += step
            idx += 1

        return segments

    async def chunk_video(self, file_path: str) -> list[MediaSegment]:
        """Split a video file into segments using ffmpeg.

        Probes the video for duration and audio track presence, then
        splits into segments using ffmpeg's -ss/-t arguments.

        Args:
            file_path: Path to the video file (mp4).

        Returns:
            List of MediaSegment objects, one per chunk.
        """
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            raise RuntimeError(
                "ffmpeg and ffprobe are both required for video chunking "
                "but not found on PATH"
            )

        _, vid_audio_max, vid_noaudio_max, overlap = _load_media_config()

        duration = await self._probe_duration(file_path)
        has_audio = await self._probe_has_audio(file_path)
        max_seconds = vid_audio_max if has_audio else vid_noaudio_max

        # Size-aware: short high-bitrate video can exceed Gemini's inline_data limit
        max_file_bytes = _get_max_single_file_bytes()
        file_size = os.path.getsize(file_path)

        if duration <= max_seconds and file_size <= max_file_bytes:
            return [
                MediaSegment(
                    file_path=file_path,
                    start_seconds=0.0,
                    end_seconds=duration,
                    has_audio=has_audio,
                    mime_type="video/mp4",
                )
            ]

        # If file is oversized but short, reduce segment duration to fit
        if file_size > max_file_bytes and duration > 0:
            bytes_per_second = file_size / duration
            size_limited_max = (max_file_bytes * 0.95) / bytes_per_second
            max_seconds = min(max_seconds, size_limited_max)
            max_seconds = max(1.0, max_seconds)

        temp_dir = self._get_temp_dir()
        segments: list[MediaSegment] = []
        step = max(1, max_seconds - overlap)

        start = 0.0
        idx = 0

        while start < duration:
            seg_duration = min(max_seconds, duration - start)
            segment_path = os.path.join(temp_dir, f"video_seg_{idx}.mp4")

            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start),
                "-i", file_path,
                "-t", str(seg_duration),
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                segment_path,
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.warning(
                    f"ffmpeg segment {idx} failed (rc={proc.returncode}): "
                    f"{stderr.decode(errors='replace')[:200]}. "
                    f"Returning {len(segments)} partial segments."
                )
                break

            segments.append(
                MediaSegment(
                    file_path=segment_path,
                    start_seconds=start,
                    end_seconds=start + seg_duration,
                    has_audio=has_audio,
                    mime_type="video/mp4",
                )
            )

            start += step
            idx += 1

        return segments

    @staticmethod
    async def _probe_duration(file_path: str) -> float:
        """Get video duration in seconds via ffprobe."""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        try:
            return float(stdout.decode().strip())
        except (ValueError, AttributeError):
            raise RuntimeError(f"Could not determine duration for {file_path}")

    @staticmethod
    async def _probe_has_audio(file_path: str) -> bool:
        """Check if the video has an audio stream via ffprobe."""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=codec_type",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return bool(stdout.decode().strip())
