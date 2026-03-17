"""Unit tests for MediaChunker.

Tests are skipped if ffmpeg is not installed on the system.
Audio tests mock pydub; video tests mock ffmpeg subprocess calls.
"""

import shutil
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.platform.chunkers.media import (
    AUDIO_MAX_SECONDS,
    OVERLAP_SECONDS,
    VIDEO_AUDIO_MAX_SECONDS,
    VIDEO_NOAUDIO_MAX_SECONDS,
    MediaChunker,
    MediaSegment,
)


# ---------------------------------------------------------------------------
# Audio chunking
# ---------------------------------------------------------------------------


class TestChunkAudio:
    @pytest.mark.asyncio
    async def test_short_audio_returns_single_segment(self, tmp_path):
        """Audio shorter than AUDIO_MAX_SECONDS -> 1 segment (original file)."""
        audio_file = tmp_path / "short.mp3"
        audio_file.write_bytes(b"\x00" * 100)

        chunker = MediaChunker(temp_dir=str(tmp_path / "segments"))

        with patch.object(
            chunker, "_probe_duration", new_callable=AsyncMock, return_value=30.0
        ):
            segments = await chunker.chunk_audio(str(audio_file))

        assert len(segments) == 1
        assert segments[0].file_path == str(audio_file)
        assert segments[0].start_seconds == 0.0
        assert segments[0].end_seconds == 30.0
        assert segments[0].has_audio is True

    @pytest.mark.asyncio
    async def test_long_audio_produces_overlapping_segments(self, tmp_path):
        """Audio longer than limit -> multiple segments via ffmpeg."""
        audio_file = tmp_path / "long.mp3"
        audio_file.write_bytes(b"\x00" * 100)

        chunker = MediaChunker(temp_dir=str(tmp_path / "segments"))

        async def mock_ffmpeg_segment(*args, **kwargs):
            proc = MagicMock()
            proc.returncode = 0
            proc.communicate = AsyncMock(return_value=(b"", b""))
            return proc

        with patch.object(
            chunker, "_probe_duration", new_callable=AsyncMock, return_value=180.0
        ), patch(
            "asyncio.create_subprocess_exec", side_effect=mock_ffmpeg_segment
        ):
            segments = await chunker.chunk_audio(str(audio_file))

        # 180s / step(75-5=70) = 3 segments
        assert len(segments) >= 3
        assert segments[0].start_seconds == 0.0

    @pytest.mark.asyncio
    async def test_audio_at_exact_limit(self, tmp_path):
        """Audio exactly at AUDIO_MAX_SECONDS -> 1 segment."""
        audio_file = tmp_path / "exact.mp3"
        audio_file.write_bytes(b"\x00" * 100)

        chunker = MediaChunker()

        with patch.object(
            chunker, "_probe_duration", new_callable=AsyncMock,
            return_value=float(AUDIO_MAX_SECONDS),
        ):
            segments = await chunker.chunk_audio(str(audio_file))

        assert len(segments) == 1

    @pytest.mark.asyncio
    async def test_short_but_oversized_audio_forces_split(self, tmp_path):
        """A short audio file (40s) that exceeds 19MB must be split by size."""
        audio_file = tmp_path / "big_short.wav"
        # Create a 25MB file (over the 19MB limit)
        audio_file.write_bytes(b"\x00" * (25 * 1024 * 1024))

        chunker = MediaChunker(temp_dir=str(tmp_path / "segments"))

        async def mock_ffmpeg_segment(*args, **kwargs):
            proc = MagicMock()
            proc.returncode = 0
            proc.communicate = AsyncMock(return_value=(b"", b""))
            return proc

        with patch.object(
            chunker, "_probe_duration", new_callable=AsyncMock, return_value=40.0
        ), patch(
            "asyncio.create_subprocess_exec", side_effect=mock_ffmpeg_segment
        ):
            segments = await chunker.chunk_audio(str(audio_file))

        # 40s file at 25MB → ~625KB/s → size_limited_max ≈ 28.9s (with 5% margin)
        # → must produce >= 2 segments
        assert len(segments) >= 2, (
            f"Short-but-large audio must be split by size, got {len(segments)} segments"
        )


# ---------------------------------------------------------------------------
# Video chunking
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
class TestChunkVideo:
    @pytest.mark.asyncio
    async def test_short_video_returns_single_segment(self, tmp_path):
        """Video shorter than limit -> 1 segment (original file)."""
        video_file = tmp_path / "short.mp4"
        video_file.write_bytes(b"\x00" * 100)

        chunker = MediaChunker(temp_dir=str(tmp_path / "segments"))

        with patch.object(
            chunker, "_probe_duration", new_callable=AsyncMock, return_value=30.0
        ), patch.object(
            chunker, "_probe_has_audio", new_callable=AsyncMock, return_value=True
        ):
            segments = await chunker.chunk_video(str(video_file))

        assert len(segments) == 1
        assert segments[0].file_path == str(video_file)
        assert segments[0].has_audio is True

    @pytest.mark.asyncio
    async def test_long_video_with_audio(self, tmp_path):
        """Video with audio > VIDEO_AUDIO_MAX_SECONDS -> multiple segments."""
        video_file = tmp_path / "long.mp4"
        video_file.write_bytes(b"\x00" * 100)

        chunker = MediaChunker(temp_dir=str(tmp_path / "segments"))

        async def mock_ffmpeg_segment(*args, **kwargs):
            """Simulate successful ffmpeg segment creation."""
            proc = MagicMock()
            proc.returncode = 0
            proc.communicate = AsyncMock(return_value=(b"", b""))
            return proc

        with patch.object(
            chunker, "_probe_duration", new_callable=AsyncMock, return_value=200.0
        ), patch.object(
            chunker, "_probe_has_audio", new_callable=AsyncMock, return_value=True
        ), patch(
            "asyncio.create_subprocess_exec", side_effect=mock_ffmpeg_segment
        ):
            segments = await chunker.chunk_video(str(video_file))

        # 200s / (120-5) step = ~1.74, so 2 segments (settings default is 120s)
        assert len(segments) >= 2

    @pytest.mark.asyncio
    async def test_video_without_audio_uses_higher_limit(self, tmp_path):
        """Video without audio uses VIDEO_NOAUDIO_MAX_SECONDS."""
        video_file = tmp_path / "silent.mp4"
        video_file.write_bytes(b"\x00" * 100)

        chunker = MediaChunker(temp_dir=str(tmp_path / "segments"))

        with patch.object(
            chunker, "_probe_duration", new_callable=AsyncMock, return_value=100.0
        ), patch.object(
            chunker, "_probe_has_audio", new_callable=AsyncMock, return_value=False
        ):
            segments = await chunker.chunk_video(str(video_file))

        # 100s < 115s limit -> 1 segment
        assert len(segments) == 1

    @pytest.mark.asyncio
    async def test_ffmpeg_not_found(self, tmp_path):
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"\x00" * 100)

        chunker = MediaChunker()

        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="ffmpeg and ffprobe are both required"):
                await chunker.chunk_video(str(video_file))

    @pytest.mark.asyncio
    async def test_size_aware_video_splitting(self, tmp_path):
        """Short high-bitrate video exceeding 20MB should be split by size."""
        video_file = tmp_path / "highbitrate.mp4"
        # 25MB file, 30 seconds — under duration limit but over size limit
        video_file.write_bytes(b"\x00" * (25 * 1024 * 1024))

        chunker = MediaChunker(temp_dir=str(tmp_path / "segments"))

        async def mock_ffmpeg_segment(*args, **kwargs):
            import os as _os

            cmd_args = args
            seg_path = cmd_args[-1] if isinstance(cmd_args[-1], str) else None
            if seg_path and seg_path.endswith(".mp4"):
                _os.makedirs(_os.path.dirname(seg_path), exist_ok=True)
                with open(seg_path, "wb") as f:
                    f.write(b"\x00" * 100)
            proc = MagicMock()
            proc.returncode = 0
            proc.communicate = AsyncMock(return_value=(b"", b""))
            return proc

        with patch.object(
            chunker, "_probe_duration", new_callable=AsyncMock, return_value=30.0
        ), patch.object(
            chunker, "_probe_has_audio", new_callable=AsyncMock, return_value=True
        ), patch(
            "asyncio.create_subprocess_exec", side_effect=mock_ffmpeg_segment
        ):
            segments = await chunker.chunk_video(str(video_file))

        # Even though 30s < 120s duration limit, file is 25MB > 19MB size limit
        # So it should be split into multiple segments
        assert len(segments) >= 2

    @pytest.mark.asyncio
    async def test_small_video_not_split(self, tmp_path):
        """Video under both duration and size limits returns as-is."""
        video_file = tmp_path / "small.mp4"
        video_file.write_bytes(b"\x00" * 1000)  # Tiny file

        chunker = MediaChunker()

        with patch.object(
            chunker, "_probe_duration", new_callable=AsyncMock, return_value=10.0
        ), patch.object(
            chunker, "_probe_has_audio", new_callable=AsyncMock, return_value=True
        ):
            segments = await chunker.chunk_video(str(video_file))

        assert len(segments) == 1
        assert segments[0].file_path == str(video_file)


# ---------------------------------------------------------------------------
# Audio chunker — ffmpeg+ffprobe requirement
# ---------------------------------------------------------------------------


class TestChunkAudioRequirements:
    @pytest.mark.asyncio
    async def test_audio_requires_ffmpeg_and_ffprobe(self, tmp_path):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"\x00" * 100)

        chunker = MediaChunker()

        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="ffmpeg and ffprobe are both required"):
                await chunker.chunk_audio(str(audio_file))


# ---------------------------------------------------------------------------
# MediaSegment dataclass
# ---------------------------------------------------------------------------


class TestMediaSegment:
    def test_creation(self):
        seg = MediaSegment(
            file_path="/tmp/seg.mp3",
            start_seconds=0.0,
            end_seconds=75.0,
            has_audio=True,
            mime_type="audio/mpeg",
        )
        assert seg.file_path == "/tmp/seg.mp3"
        assert seg.has_audio is True
        assert seg.mime_type == "audio/mpeg"
