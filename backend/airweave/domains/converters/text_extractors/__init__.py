"""Text extraction utilities for various document formats."""

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
