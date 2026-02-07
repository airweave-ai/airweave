"""Direct text extraction from PDFs with embedded text layers.

Uses PyMuPDF (fitz) to extract text directly from PDF objects, bypassing OCR
entirely for born-digital PDFs. This is orders of magnitude faster and cheaper
than OCR for documents that have a text layer.

The module detects whether the whole PDF has extractable text:
- If all pages have sufficient text → return extracted content
- If any page is image-only → caller should use OCR for whole PDF
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field

from airweave.core.logging import logger
from airweave.platform.sync.exceptions import SyncFailureError

# Minimum characters per page to consider it "has text layer".
# Pages below this threshold are treated as image-only.
MIN_CHARS_PER_PAGE = 50


@dataclass
class PageExtractionResult:
    """Result of attempting text extraction on a single page.

    Attributes:
        page_num: 0-based page number.
        text: Extracted text (empty string if extraction failed or page is image-only).
        needs_ocr: True if this page should be sent to OCR.
    """

    page_num: int
    text: str
    needs_ocr: bool


@dataclass
class PdfExtractionResult:
    """Result of extracting text from an entire PDF.

    Attributes:
        path: Original PDF path.
        pages: Per-page extraction results.
    """

    path: str
    pages: list[PageExtractionResult] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        """Combined text from all extracted pages."""
        texts = [p.text for p in self.pages if p.text and not p.needs_ocr]
        return "\n\n".join(texts)

    @property
    def pages_needing_ocr(self) -> list[int]:
        """0-based page numbers that need OCR."""
        return [p.page_num for p in self.pages if p.needs_ocr]

    @property
    def extraction_ratio(self) -> float:
        """Fraction of pages that were successfully extracted."""
        if not self.pages:
            return 0.0
        extracted = sum(1 for p in self.pages if not p.needs_ocr)
        return extracted / len(self.pages)

    @property
    def fully_extracted(self) -> bool:
        """True if all pages were extracted without needing OCR."""
        return bool(self.pages) and len(self.pages_needing_ocr) == 0


async def extract_pdf_text(path: str) -> PdfExtractionResult:
    """Extract text from a PDF, detecting which pages need OCR.

    Args:
        path: Path to the PDF file.

    Returns:
        A :class:`PdfExtractionResult` with per-page extraction results.

    Raises:
        SyncFailureError: If PyMuPDF is not installed.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise SyncFailureError("PyMuPDF (fitz) required for PDF text extraction but not installed")

    def _extract() -> PdfExtractionResult:
        result = PdfExtractionResult(path=path)

        try:
            doc = fitz.open(path)
        except Exception as exc:
            logger.warning(f"Failed to open PDF {os.path.basename(path)}: {exc}")
            return result

        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_result = _extract_page(page, page_num)
                result.pages.append(page_result)
        finally:
            doc.close()

        # Log summary
        name = os.path.basename(path)
        total = len(result.pages)
        extracted = total - len(result.pages_needing_ocr)
        ocr_needed = len(result.pages_needing_ocr)

        if ocr_needed == 0:
            logger.debug(f"PDF {name}: all {total} pages have text layer")
        elif extracted == 0:
            logger.debug(f"PDF {name}: all {total} pages are image-only (scanned)")
        else:
            logger.debug(
                f"PDF {name}: {extracted}/{total} pages have text, {ocr_needed} are image-only"
            )

        return result

    return await asyncio.to_thread(_extract)


def _extract_page(page, page_num: int) -> PageExtractionResult:
    """Extract text from a single PDF page.

    Args:
        page: PyMuPDF page object.
        page_num: 0-based page number.

    Returns:
        A :class:`PageExtractionResult`.
    """
    try:
        # Extract text with layout preservation
        text = page.get_text("text")
        char_count = len(text.strip())

        if char_count < MIN_CHARS_PER_PAGE:
            return PageExtractionResult(
                page_num=page_num,
                text="",
                needs_ocr=True,
            )

        # Check if page is primarily images with minimal text
        image_list = page.get_images()
        if image_list and char_count < 200:
            # Has images and very little text - likely a scan
            return PageExtractionResult(
                page_num=page_num,
                text="",
                needs_ocr=True,
            )

        # Text extraction successful
        return PageExtractionResult(
            page_num=page_num,
            text=text.strip(),
            needs_ocr=False,
        )

    except Exception as exc:
        logger.warning(f"Text extraction failed for page {page_num}: {exc}")
        return PageExtractionResult(
            page_num=page_num,
            text="",
            needs_ocr=True,
        )


def text_to_markdown(text: str) -> str:
    """Convert extracted plain text to basic Markdown.

    Applies simple heuristics to detect headings, lists, and paragraphs.

    Args:
        text: Raw extracted text.

    Returns:
        Markdown-formatted text.
    """
    if not text:
        return ""

    lines = text.split("\n")
    result_lines: list[str] = []
    prev_blank = True

    for line in lines:
        stripped = line.strip()

        if not stripped:
            if not prev_blank:
                result_lines.append("")
                prev_blank = True
            continue

        prev_blank = False

        # Detect potential headings (short lines, possibly all caps or title case)
        is_short = len(stripped) < 80
        is_uppercase = stripped.isupper() and len(stripped) > 3
        is_titlecase = stripped.istitle() and len(stripped) < 60

        # Detect bullet points
        if stripped.startswith(("• ", "· ", "- ", "* ", "◦ ")):
            result_lines.append(f"- {stripped[2:].strip()}")
        elif stripped.startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
            result_lines.append(stripped)
        # Potential heading
        elif is_short and (is_uppercase or is_titlecase) and not stripped.endswith((".", ",", ";")):
            if is_uppercase:
                result_lines.append(f"## {stripped.title()}")
            else:
                result_lines.append(f"## {stripped}")
        else:
            result_lines.append(stripped)

    return "\n".join(result_lines)
