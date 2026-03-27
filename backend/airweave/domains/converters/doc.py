"""Legacy .doc converter with hybrid text extraction + OCR fallback."""

from __future__ import annotations

from typing import Optional

from airweave.domains.converters._base import HybridDocumentConverter
from airweave.domains.converters.text_extractors.doc import extract_doc_text


class DocConverter(HybridDocumentConverter):
    """Converts legacy .doc files to text using OLE2 extraction with OCR fallback."""

    async def _try_extract(self, path: str) -> Optional[str]:
        return await extract_doc_text(path)
