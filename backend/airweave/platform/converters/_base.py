"""Base converter interfaces for text converters."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from airweave.core.logging import logger
from airweave.core.protocols.ocr import OcrProvider


class BaseTextConverter(ABC):
    """Base class for all text converters."""

    @abstractmethod
    async def convert_batch(self, file_paths: List[str]) -> Dict[str, str]:
        """Batch convert files to markdown text.

        Args:
            file_paths: List of file paths to convert

        Returns:
            Dict mapping file_path -> markdown text content
        """
        pass


class HybridDocumentConverter(BaseTextConverter):
    """Converter that tries cheap local text extraction before falling back to OCR.

    Subclasses implement :meth:`_try_extract` for format-specific extraction.
    The shared :meth:`convert_batch` handles the extract-first / OCR-fallback
    orchestration so each format only needs to provide the extraction logic.

    Usage::

        class DocxConverter(HybridDocumentConverter):
            async def _try_extract(self, path: str) -> Optional[str]:
                return await extract_docx_text(path)


        converter = DocxConverter(ocr_provider=MistralOCR())
    """

    def __init__(self, ocr_provider: Optional[OcrProvider] = None) -> None:
        """Initialize the converter.

        Args:
            ocr_provider: OCR provider for fallback. If ``None``, files that
                          cannot be text-extracted will return ``None``.
        """
        self._ocr_provider = ocr_provider

    @abstractmethod
    async def _try_extract(self, path: str) -> Optional[str]:
        """Attempt local text extraction for a single file.

        Returns:
            Extracted markdown if successful, or ``None`` if OCR is needed.
        """

    async def convert_batch(self, file_paths: List[str]) -> Dict[str, Optional[str]]:
        """Convert files to markdown, trying extraction first.

        For each file, calls :meth:`_try_extract`. If that returns content,
        uses it directly (0 API calls). Otherwise, batches the file for OCR.

        Args:
            file_paths: Local file paths to convert.

        Returns:
            Mapping of ``file_path -> markdown`` (``None`` on failure).
        """
        results: Dict[str, Optional[str]] = {}
        needs_ocr: List[str] = []

        for path in file_paths:
            name = os.path.basename(path)
            try:
                markdown = await self._try_extract(path)
                if markdown:
                    results[path] = markdown
                    logger.debug(f"{name}: extracted via text layer")
                else:
                    logger.debug(f"{name}: text extraction insufficient, needs OCR")
                    needs_ocr.append(path)
            except Exception as exc:
                logger.warning(f"{name}: extraction error ({exc}), needs OCR")
                needs_ocr.append(path)

        if needs_ocr:
            if self._ocr_provider is None:
                logger.warning(f"No OCR converter configured, {len(needs_ocr)} files will fail")
                for path in needs_ocr:
                    results[path] = None
            else:
                ocr_results = await self._ocr_provider.convert_batch(needs_ocr)
                results.update(ocr_results)

        return results
