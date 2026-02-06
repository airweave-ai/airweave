"""Image compression for oversized images before Mistral OCR upload.

Uses Pillow to iteratively reduce JPEG quality until the file fits within
the Mistral upload limit.  PNG files are first converted to JPEG.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from typing import TYPE_CHECKING

from airweave.core.logging import logger

if TYPE_CHECKING:
    from PIL import Image
from airweave.platform.ocr.mistral.models import CompressionResult
from airweave.platform.sync.exceptions import EntityProcessingError, SyncFailureError

# Quality levels to try, from highest to lowest.
_QUALITY_STEPS = range(85, 19, -10)


async def compress_image(path: str, max_bytes: int) -> CompressionResult:
    """Compress an image so it fits within *max_bytes*.

    Args:
        path: Path to the original image file.
        max_bytes: Maximum allowed file size in bytes.

    Returns:
        A :class:`CompressionResult` with the output path and whether it is
        a temp file.  If no compression was needed the original *path* is
        returned with ``is_temp=False``.

    Raises:
        SyncFailureError: If Pillow is not installed.
        EntityProcessingError: If the image cannot be compressed enough.
    """
    file_size = os.path.getsize(path)

    if file_size <= max_bytes:
        return CompressionResult(path=path, is_temp=False)

    try:
        from PIL import Image
    except ImportError:
        raise SyncFailureError("Pillow package required for image compression but not installed")

    def _compress() -> str:
        img = Image.open(path)
        _, ext = os.path.splitext(path)
        ext = ext.lower()

        if ext == ".png":
            return _compress_png_as_jpeg(img, path, file_size, max_bytes)
        return _compress_jpeg(img, path, ext, file_size, max_bytes)

    result_path = await asyncio.to_thread(_compress)
    return CompressionResult(path=result_path, is_temp=True)


# ---------------------------------------------------------------------------
# Internal helpers (run inside ``asyncio.to_thread``)
# ---------------------------------------------------------------------------


def _compress_png_as_jpeg(
    img: "Image.Image",
    original_path: str,
    original_size: int,
    max_bytes: int,
) -> str:
    """Convert PNG to JPEG and compress."""
    from PIL import Image

    # Convert RGBA / palette modes to RGB.
    if img.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        mask = img.split()[-1] if img.mode == "RGBA" else None
        background.paste(img, mask=mask)
        img = background

    for quality in _QUALITY_STEPS:
        fd, temp_path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)

        img.save(temp_path, "JPEG", quality=quality, optimize=True)
        compressed_size = os.path.getsize(temp_path)

        if compressed_size <= max_bytes:
            _log_compression(original_path, original_size, compressed_size, quality, "PNG->JPEG")
            return temp_path

        os.unlink(temp_path)

    _raise_incompressible(original_path, original_size, max_bytes)


def _compress_jpeg(
    img: "Image.Image",
    original_path: str,
    ext: str,
    original_size: int,
    max_bytes: int,
) -> str:
    """Compress a JPEG by reducing quality."""
    for quality in _QUALITY_STEPS:
        fd, temp_path = tempfile.mkstemp(suffix=ext)
        os.close(fd)

        img.save(temp_path, quality=quality, optimize=True)
        compressed_size = os.path.getsize(temp_path)

        if compressed_size <= max_bytes:
            _log_compression(original_path, original_size, compressed_size, quality, "JPEG")
            return temp_path

        os.unlink(temp_path)

    _raise_incompressible(original_path, original_size, max_bytes)


# ---------------------------------------------------------------------------
# Logging / error helpers
# ---------------------------------------------------------------------------


def _log_compression(path: str, original: int, compressed: int, quality: int, label: str) -> None:
    logger.debug(
        f"Compressed {label} {os.path.basename(path)}: "
        f"{original / 1_000_000:.2f}MB -> {compressed / 1_000_000:.2f}MB (quality={quality}%)"
    )


def _raise_incompressible(path: str, original_size: int, max_bytes: int) -> None:
    raise EntityProcessingError(
        f"Cannot compress {os.path.basename(path)} below {max_bytes / 1_000_000:.2f}MB "
        f"(original: {original_size / 1_000_000:.2f}MB)"
    )
