"""Video-to-text converter using scene-based keyframe OCR + audio transcription.

Two-pronged approach:
1. Visual OCR: Extracts keyframes via ffmpeg scene detection (only when
   the screen content changes), then OCRs each frame via Docling/Mistral
   OCR or falls back to Gemini vision.
2. Audio transcription: Extracts and transcribes the audio track.

Both are combined into textual_representation for BM25 and answer generation.
Scene detection threshold and max frames are configurable via settings.
"""

import asyncio
import os
import tempfile
from typing import Dict, List, Optional

from airweave.core.logging import logger
from airweave.platform.converters._base import BaseTextConverter


def _get_scene_threshold() -> float:
    """Read configurable scene detection threshold from settings."""
    try:
        from airweave.core.config import settings

        return getattr(settings, "MULTIMODAL_VIDEO_SCENE_THRESHOLD", 0.3)
    except Exception:
        return 0.3


def _get_max_keyframes() -> int:
    """Read configurable max keyframes per video from settings."""
    try:
        from airweave.core.config import settings

        return getattr(settings, "MULTIMODAL_VIDEO_MAX_KEYFRAMES", 30)
    except Exception:
        return 30


# Timeout for Gemini generate_content calls (seconds)
_OCR_TIMEOUT: float = 60.0


class VideoConverter(BaseTextConverter):
    """Convert video to text via scene-based keyframe OCR + audio transcription.

    For each video:
    1. Extract keyframes at scene changes via ffmpeg (plus first frame)
    2. OCR each keyframe via the existing OCR provider (Docling/Mistral)
    3. Deduplicate consecutive OCR text
    4. Transcribe audio track
    5. Combine into textual_representation
    """

    BATCH_SIZE: int = 1

    def __init__(self, *, gemini_api_key: str | None = None) -> None:
        self._api_key = gemini_api_key
        self._client = None

    async def convert_batch(self, file_paths: List[str]) -> Dict[str, Optional[str]]:
        """Convert videos to text via keyframe OCR + audio."""
        results: Dict[str, Optional[str]] = {}

        for path in file_paths:
            name = os.path.basename(path)
            try:
                text = await self._convert_video(path)
                if text and text.strip():
                    results[path] = text
                    logger.debug(f"{name}: video converted via keyframe OCR + audio")
                else:
                    results[path] = f"[Video: {name}]"
                    logger.info(f"{name}: video conversion returned no content")
            except Exception as e:
                logger.warning(f"{name}: video conversion failed: {e}")
                results[path] = f"[Video: {name}]"

        return results

    async def _convert_video(self, video_path: str) -> Optional[str]:
        """Convert a video using keyframe OCR and audio transcription."""
        parts: list[str] = []

        # 1. Scene-based keyframe OCR
        ocr_text = await self._ocr_keyframes(video_path)
        if ocr_text:
            parts.append(f"## Visual Content (OCR)\n{ocr_text}")

        # 2. Audio transcription
        transcript = await self._extract_and_transcribe(video_path)
        if transcript:
            parts.append(f"## Audio Transcript\n{transcript}")

        if not parts:
            return None

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Keyframe OCR
    # ------------------------------------------------------------------

    async def _ocr_keyframes(self, video_path: str) -> Optional[str]:
        """Extract keyframes at scene changes and OCR each one.

        Uses ffmpeg's scene detection filter to only capture frames when
        the visual content changes significantly. This is efficient for
        screen recordings and presentations.
        """
        threshold = _get_scene_threshold()
        max_frames = _get_max_keyframes()

        tmpdir = tempfile.mkdtemp(prefix="airweave_keyframes_")

        try:
            # Extract first frame + keyframes at scene changes.
            # eq(n,0) ensures frame 0 is always included (static videos
            # would otherwise yield zero keyframes).
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vf", f"select='eq(n\\,0)+gt(scene\\,{threshold})',showinfo",
                "-vsync", "vfr",
                "-frames:v", str(max_frames),
                "-q:v", "2",  # High quality JPEG
                os.path.join(tmpdir, "frame_%04d.jpg"),
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.warning(
                    f"Keyframe extraction failed: {stderr.decode(errors='replace')[:200]}"
                )
                return None

            # Collect extracted frames
            frames = sorted(
                [
                    os.path.join(tmpdir, f)
                    for f in os.listdir(tmpdir)
                    if f.endswith(".jpg")
                ]
            )

            if not frames:
                logger.info("No keyframes extracted (video may be static)")
                return None

            logger.info(
                f"Extracted {len(frames)} keyframes from "
                f"{os.path.basename(video_path)} (threshold={threshold})"
            )

            # OCR each frame
            ocr_texts = await self._ocr_frames(frames)

            # Deduplicate consecutive similar texts
            deduped = self._deduplicate_texts(ocr_texts)

            if not deduped:
                return None

            return "\n\n---\n\n".join(deduped)

        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)

    async def _ocr_frames(self, frame_paths: list[str]) -> list[str]:
        """OCR a list of frame images using the existing OCR provider.

        Falls back to Gemini vision if no OCR provider is available.
        """
        texts: list[str] = []

        # Try Docling/Mistral OCR first (free/existing)
        try:
            from airweave.platform import converters

            ocr_provider = converters.img_converter
            if ocr_provider is not None:
                results = await ocr_provider.convert_batch(frame_paths)
                for path in frame_paths:
                    text = results.get(path)
                    if text and text.strip():
                        texts.append(text.strip())
                    else:
                        texts.append("")
                return texts
        except Exception as e:
            logger.debug(f"OCR provider not available: {e}")

        # Fallback: Gemini vision per frame
        for path in frame_paths:
            text = await self._gemini_ocr_frame(path)
            texts.append(text or "")

        return texts

    def _get_client(self):
        """Lazily create and cache the Gemini client."""
        if self._client is not None:
            return self._client

        from google import genai

        api_key = self._api_key
        if not api_key:
            from airweave.core.config import settings

            api_key = settings.GEMINI_API_KEY

        if not api_key:
            return None

        self._client = genai.Client(api_key=api_key)
        return self._client

    @staticmethod
    def _get_transcription_model() -> str:
        """Read configurable transcription model from settings."""
        try:
            from airweave.core.config import settings

            return getattr(settings, "MULTIMODAL_TRANSCRIPTION_MODEL", "gemini-3-flash-preview")
        except Exception:
            return "gemini-3-flash-preview"

    async def _gemini_ocr_frame(self, frame_path: str) -> Optional[str]:
        """OCR a single frame using Gemini generate_content."""
        try:
            import aiofiles
            from google.genai.types import Blob, Part

            async with aiofiles.open(frame_path, "rb") as f:
                img_bytes = await f.read()

            client = self._get_client()
            if not client:
                return None

            part = Part(inline_data=Blob(data=img_bytes, mime_type="image/jpeg"))
            model = self._get_transcription_model()

            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=model,
                    contents=[
                        "Extract ALL text visible in this screenshot. "
                        "Include UI labels, button text, chat messages, "
                        "names, and any other readable text. "
                        "Return only the extracted text, no commentary.",
                        part,
                    ],
                ),
                timeout=_OCR_TIMEOUT,
            )

            if response and response.text:
                return response.text.strip()
        except Exception as e:
            logger.debug(f"Gemini OCR failed for {frame_path}: {e}")

        return None

    @staticmethod
    def _deduplicate_texts(texts: list[str]) -> list[str]:
        """Remove consecutive texts that are >80% similar.

        Screen recordings often have many frames with the same text.
        Only keep a frame's text if it's meaningfully different from
        the previous one.
        """
        if not texts:
            return []

        deduped: list[str] = []
        prev = ""

        for text in texts:
            if not text:
                continue

            # Simple similarity: shared character ratio
            if prev:
                shorter = min(len(prev), len(text))
                if shorter > 0:
                    common = sum(1 for a, b in zip(prev, text) if a == b)
                    similarity = common / shorter
                    if similarity > 0.8:
                        continue  # Too similar to previous, skip

            deduped.append(text)
            prev = text

        return deduped

    # ------------------------------------------------------------------
    # Audio transcription
    # ------------------------------------------------------------------

    async def _extract_and_transcribe(self, video_path: str) -> Optional[str]:
        """Extract audio track from video and transcribe."""
        has_audio = await self._has_audio_track(video_path)
        if not has_audio:
            return None

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            audio_path = tmp.name

        try:
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vn",
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
                    f"ffmpeg audio extraction failed: "
                    f"{stderr.decode(errors='replace')[:200]}"
                )
                return None

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
