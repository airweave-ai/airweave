"""PDF converter with hybrid text extraction + OCR fallback.

Uses :class:`HybridDocumentConverter` to try PyMuPDF text extraction first
and fall back to OCR only when pages lack a text layer.
"""

from __future__ import annotations

from typing import Optional

from airweave.platform.converters._base import HybridDocumentConverter
from airweave.platform.converters.text_extractors.pdf import (
    extract_pdf_text,
    text_to_markdown,
)


class PdfConverter(HybridDocumentConverter):
    """Converts PDFs to markdown using text extraction with OCR fallback.

    For PDFs with embedded text layers on ALL pages, text is extracted directly
    without any API calls.  If any page lacks a text layer, the entire PDF is
    sent to the OCR provider.

    Usage::

        converter = PdfConverter(ocr_provider=MistralOCR())
        results = await converter.convert_batch(["/tmp/doc.pdf"])
    """

    async def _try_extract(self, path: str) -> Optional[str]:
        """Extract text from a PDF using PyMuPDF.

        Returns markdown if all pages have a text layer, ``None`` otherwise.
        """
        extraction = await extract_pdf_text(path)

        if extraction.fully_extracted and extraction.full_text:
            return text_to_markdown(extraction.full_text)

        return None
