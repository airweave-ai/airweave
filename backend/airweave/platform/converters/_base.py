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

    @staticmethod
    def _try_read_as_text(path: str, max_probe_bytes: int = 8192) -> Optional[str]:
        """Check if a file is actually plain text despite its extension.

        Reads a small probe of the file and checks if it decodes as valid UTF-8
        with a low ratio of control characters. This catches files that have
        binary extensions (e.g. .docx, .pdf) but actually contain plain text --
        common with auto-generated test data or legacy systems.

        Args:
            path: Path to the file.
            max_probe_bytes: How many bytes to probe for text detection.

        Returns:
            Full file content as string if it's valid text, None otherwise.
        """
        try:
            with open(path, "rb") as f:
                probe = f.read(max_probe_bytes)

            if not probe:
                return None

            # Try UTF-8 decode on the probe
            try:
                probe.decode("utf-8")
            except UnicodeDecodeError:
                return None

            # Check for excessive control characters (binary indicator)
            # Allow common whitespace: \n, \r, \t
            control_count = sum(1 for b in probe if b < 32 and b not in (9, 10, 13))
            if control_count / len(probe) > 0.05:  # >5% control chars = binary
                return None

            # It's text -- read the full file
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # Must have meaningful content
            if len(content.strip()) < 10:
                return None

            return content

        except Exception:
            return None

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
                    # Before falling back to OCR, check if the file is actually
                    # plain text with a misleading extension (e.g. .docx containing text)
                    text_content = self._try_read_as_text(path)
                    if text_content:
                        results[path] = text_content
                        logger.info(
                            f"{name}: extension suggests binary but content is plain text, "
                            "using text fallback instead of OCR"
                        )
                    else:
                        logger.debug(f"{name}: text extraction insufficient, needs OCR")
                        needs_ocr.append(path)
            except Exception as exc:
                logger.warning(f"{name}: extraction error ({exc}), needs OCR")
                # Same fallback check on extraction errors
                text_content = self._try_read_as_text(path)
                if text_content:
                    results[path] = text_content
                    logger.info(
                        f"{name}: extraction failed but content is plain text, "
                        "using text fallback instead of OCR"
                    )
                else:
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
