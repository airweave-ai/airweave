"""Text extraction utilities for various document formats.

Re-exports all extractor functions and result types for convenience::

    from airweave.platform.converters.text_extractors import extract_pdf_text
    from airweave.platform.converters.text_extractors import extract_docx_text
    from airweave.platform.converters.text_extractors import extract_pptx_text
"""

from .docx import extract_docx_text
from .pdf import PdfExtractionResult, extract_pdf_text, text_to_markdown
from .pptx import extract_pptx_text

__all__ = [
    "PdfExtractionResult",
    "extract_pdf_text",
    "text_to_markdown",
    "extract_docx_text",
    "extract_pptx_text",
]
