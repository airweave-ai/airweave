"""Converter registry — maps file extensions to converter instances."""

from __future__ import annotations

from typing import Dict, Optional

from airweave.domains.converters._base import BaseTextConverter, OcrConverterAdapter
from airweave.domains.converters.code import CodeConverter
from airweave.domains.converters.doc import DocConverter
from airweave.domains.converters.docx import DocxConverter
from airweave.domains.converters.html import HtmlConverter
from airweave.domains.converters.pdf import PdfConverter
from airweave.domains.converters.pptx import PptxConverter
from airweave.domains.converters.protocols import ConverterRegistryProtocol
from airweave.domains.converters.txt import TxtConverter
from airweave.domains.converters.web import WebConverter
from airweave.domains.converters.xlsx import XlsxConverter
from airweave.domains.ocr.protocols import OcrProvider


class ConverterRegistry(ConverterRegistryProtocol):
    """Concrete registry that creates and owns all converter instances.

    Built once by the container factory with the resolved OCR provider.
    """

    def __init__(self, ocr_provider: Optional[OcrProvider] = None) -> None:
        """Build all converter instances and the extension mapping."""
        pdf = PdfConverter(ocr_provider=ocr_provider)
        doc = DocConverter(ocr_provider=ocr_provider)
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
            ".doc": doc,
            ".docx": docx,
            ".pptx": pptx,
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

        # Image extensions only available when OCR is configured
        if ocr_provider is not None:
            ocr_adapter = OcrConverterAdapter(ocr_provider)
            self._extension_map.update(
                {
                    ".jpg": ocr_adapter,
                    ".jpeg": ocr_adapter,
                    ".png": ocr_adapter,
                }
            )

    def for_extension(self, ext: str) -> Optional[BaseTextConverter]:
        """Return the converter for a given file extension, or None."""
        return self._extension_map.get(ext)

    def for_web(self) -> BaseTextConverter:
        """Return the web converter."""
        return self._web
