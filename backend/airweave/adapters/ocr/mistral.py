"""Mistral OCR adapter.

Thin adapter that delegates to the platform MistralOCR implementation,
exposing it through the adapters layer for dependency injection.

Satisfies the :class:`~airweave.core.protocols.ocr.OcrProvider` protocol.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from airweave.platform.ocr.mistral.converter import MistralOCR


class MistralOcrAdapter:
    """Adapter for Mistral OCR.

    Wraps :class:`~airweave.platform.ocr.mistral.converter.MistralOCR`
    so callers depend on the adapter layer rather than reaching into platform
    internals.

    Usage::

        ocr: OcrProvider = MistralOcrAdapter()
        results = await ocr.convert_batch(["/tmp/doc.pdf"])
    """

    def __init__(self, concurrency: int = 10) -> None:
        """Initialize the adapter.

        Args:
            concurrency: Maximum concurrent OCR calls passed to the
                underlying Mistral client.
        """
        self._impl = MistralOCR(concurrency=concurrency)

    async def convert_batch(self, file_paths: List[str]) -> Dict[str, Optional[str]]:
        """Convert files to markdown via Mistral OCR.

        Args:
            file_paths: Local file paths (PDF, DOCX, PPTX, JPG, JPEG, PNG).

        Returns:
            Mapping of ``file_path -> markdown`` (``None`` on per-file failure).
        """
        return await self._impl.convert_batch(file_paths)
