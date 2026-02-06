"""PPTX converter with hybrid text extraction + OCR fallback.

Uses :class:`HybridDocumentConverter` to try python-pptx text extraction first
and fall back to OCR only when extraction is insufficient.
"""

from __future__ import annotations

from typing import Optional

from airweave.platform.converters._base import HybridDocumentConverter
from airweave.platform.converters.text_extractors.pptx import extract_pptx_text


class PptxConverter(HybridDocumentConverter):
    """Converts PPTX files to markdown using text extraction with OCR fallback.

    Most PPTX files have extractable text via python-pptx.  If extraction
    yields insufficient content (e.g. slides are mostly images/diagrams),
    the file is sent to the OCR provider.

    Usage::

        converter = PptxConverter(ocr_provider=MistralOCR())
        results = await converter.convert_batch(["/tmp/slides.pptx"])
    """

    async def _try_extract(self, path: str) -> Optional[str]:
        """Extract text from a PPTX using python-pptx.

        Returns markdown if sufficient text was extracted, ``None`` otherwise.
        """
        return await extract_pptx_text(path)
