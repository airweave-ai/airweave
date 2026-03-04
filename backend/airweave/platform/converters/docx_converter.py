"""DOCX converter with hybrid text extraction + OCR fallback.

Uses :class:`HybridDocumentConverter` to try python-docx text extraction first
and fall back to OCR only when extraction is insufficient.
"""

from __future__ import annotations

from typing import Optional

from airweave.platform.converters._base import HybridDocumentConverter
from airweave.platform.converters.text_extractors.docx import extract_docx_text


class DocxConverter(HybridDocumentConverter):
    """Converts DOCX files to markdown using text extraction with OCR fallback.

    Most DOCX files have extractable text via python-docx.  If extraction
    yields insufficient content (e.g. the DOCX is mostly images), the file
    is sent to the OCR provider.

    Usage::

        converter = DocxConverter(ocr_provider=MistralOCR())
        results = await converter.convert_batch(["/tmp/doc.docx"])
    """

    async def _try_extract(self, path: str) -> Optional[str]:
        """Extract text from a DOCX using python-docx.

        Returns markdown if sufficient text was extracted, ``None`` otherwise.
        """
        return await extract_docx_text(path)
