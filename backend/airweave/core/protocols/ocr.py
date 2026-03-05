"""OCR provider protocol.

Defines the structural typing contract that any OCR backend must satisfy.
Uses :class:`typing.Protocol` so implementations don't need to inherit.

Usage::

    from airweave.core.protocols.ocr import OcrProvider


    def build_pipeline(ocr: OcrProvider) -> ...:
        results = await ocr.convert_batch(["/tmp/scan.pdf"])
"""

from __future__ import annotations

from typing import Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class OcrProvider(Protocol):
    """Structural protocol for OCR providers.

    Any class that implements an async ``convert_batch`` method with this
    exact signature is considered a valid OCR provider -- no subclassing
    required.
    """

    async def convert_batch(self, file_paths: List[str]) -> Dict[str, Optional[str]]:
        """Convert files to markdown text via OCR.

        Args:
            file_paths: Local file paths to OCR.

        Returns:
            Mapping of ``file_path -> markdown`` (``None`` on failure).
        """
        ...
