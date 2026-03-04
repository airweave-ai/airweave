"""Docling OCR adapter.

Calls a docling-serve instance over HTTP, exposing it through the
adapters layer for dependency injection.

Satisfies the :class:`~airweave.core.protocols.ocr.OcrProvider` protocol.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Dict, List, Optional

import httpx

from airweave.core.logging import logger

# Docling-serve accepts these via the /v1/convert/file endpoint.
_SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".html",
    ".md",
    ".csv",
    ".png",
    ".jpg",
    ".jpeg",
    ".tiff",
    ".bmp",
    ".webp",
}


class DoclingOcrAdapter:
    """Adapter for docling-serve.

    Posts files to the ``/v1/convert/file`` endpoint of a running
    `docling-serve <https://github.com/docling-project/docling-serve>`_
    instance and returns the markdown output.

    Usage::

        ocr: OcrProvider = DoclingOcrAdapter(base_url="http://docling:5001")
        results = await ocr.convert_batch(["/tmp/doc.pdf"])
    """

    def __init__(self, base_url: str, timeout: float = 120.0) -> None:
        """Initialize the adapter.

        Args:
            base_url: Root URL of the docling-serve instance
                (e.g. ``http://docling:5001``).
            timeout: HTTP timeout in seconds per file conversion.
        """
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        try:
            response = httpx.get(f"{self._base_url}/health")
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(f"[DoclingOCR] Health check failed: {exc}")
            raise

    async def convert_batch(self, file_paths: List[str]) -> Dict[str, Optional[str]]:
        """Convert files to markdown via docling-serve.

        Args:
            file_paths: Local file paths (PDF, DOCX, PPTX, images, etc.).

        Returns:
            Mapping of ``file_path -> markdown`` (``None`` on per-file failure).
        """
        results: Dict[str, Optional[str]] = {}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for path in file_paths:
                results[path] = await self._convert_single(client, path)
        return results

    async def _convert_single(self, client: httpx.AsyncClient, file_path: str) -> Optional[str]:
        """Convert a single file, returning markdown or None on failure."""
        path = Path(file_path)
        if path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
            logger.warning(f"[DoclingOCR] Unsupported file type: {path.suffix}")
            return None

        content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

        try:
            with open(file_path, "rb") as f:
                response = await client.post(
                    f"{self._base_url}/v1/convert/file",
                    files={"files": (path.name, f, content_type)},
                    data={"to_formats": "md", "do_ocr": "true"},
                )
            response.raise_for_status()

            data = response.json()
            md_content = data.get("document", {}).get("md_content")
            if md_content:
                return md_content

            logger.warning(f"[DoclingOCR] Empty markdown for {file_path}")
            return None

        except httpx.HTTPStatusError as exc:
            logger.warning(f"[DoclingOCR] HTTP {exc.response.status_code} for {file_path}")
            raise
        except httpx.TimeoutException:
            logger.warning(f"[DoclingOCR] Timeout converting {file_path}")
            raise
        except Exception as exc:
            logger.warning(f"[DoclingOCR] Failed to convert {file_path}: {exc}")
            raise
