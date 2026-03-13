"""PDF converter with hybrid text extraction + OCR fallback."""

from __future__ import annotations

from typing import Optional

from airweave.domains.converters._base import HybridDocumentConverter
from airweave.domains.converters.text_extractors.pdf import (
    extract_pdf_text,
    text_to_markdown,
)


class PdfConverter(HybridDocumentConverter):
    """Converts PDFs to markdown using text extraction with OCR fallback."""

    async def _try_extract(self, path: str) -> Optional[str]:
        extraction = await extract_pdf_text(path)
        if extraction.fully_extracted and extraction.full_text:
            return text_to_markdown(extraction.full_text)
        return None
