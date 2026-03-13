"""Converter registry — maps file extensions to converter instances."""

from __future__ import annotations

from typing import Dict, Optional

from airweave.core.protocols.ocr import OcrProvider
from airweave.domains.converters._base import BaseTextConverter
from airweave.domains.converters.code import CodeConverter
from airweave.domains.converters.docx import DocxConverter
from airweave.domains.converters.html import HtmlConverter
from airweave.domains.converters.pdf import PdfConverter
from airweave.domains.converters.pptx import PptxConverter
from airweave.domains.converters.txt import TxtConverter
from airweave.domains.converters.web import WebConverter
from airweave.domains.converters.xlsx import XlsxConverter


class ConverterRegistry:
    """Concrete registry that creates and owns all converter instances.

    Built once by the container factory with the resolved OCR provider.
    """

    def __init__(self, ocr_provider: Optional[OcrProvider] = None) -> None:
        """Build all converter instances and the extension mapping."""
        pdf = PdfConverter(ocr_provider=ocr_provider)
        docx = DocxConverter(ocr_provider=ocr_provider)
        pptx = PptxConverter(ocr_provider=ocr_provider)
        html = HtmlConverter()
        txt = TxtConverter()
        xlsx = XlsxConverter()
        code = CodeConverter()
        self._web = WebConverter()

        self._extension_map: Dict[str, BaseTextConverter] = {
            # Documents — text extraction + OCR fallback
            ".pdf": pdf,
            ".docx": docx,
            ".pptx": pptx,
            # Images — direct OCR (ocr_provider itself implements convert_batch)
            ".jpg": ocr_provider,
            ".jpeg": ocr_provider,
            ".png": ocr_provider,
            # Spreadsheets
            ".xlsx": xlsx,
            # HTML
            ".html": html,
            ".htm": html,
            # Text / structured text
            ".txt": txt,
            ".json": txt,
            ".xml": txt,
            ".md": txt,
            ".yaml": txt,
            ".yml": txt,
            ".toml": txt,
            # Code
            ".py": code,
            ".js": code,
            ".ts": code,
            ".tsx": code,
            ".jsx": code,
            ".java": code,
            ".cpp": code,
            ".c": code,
            ".h": code,
            ".hpp": code,
            ".go": code,
            ".rs": code,
            ".rb": code,
            ".php": code,
            ".swift": code,
            ".kt": code,
            ".kts": code,
            ".tf": code,
            ".tfvars": code,
        }

    def for_extension(self, ext: str) -> Optional[BaseTextConverter]:
        """Return the converter for a given file extension, or None."""
        return self._extension_map.get(ext)

    def for_web(self) -> BaseTextConverter:
        """Return the web converter."""
        return self._web
