"""Tests for PdfConverter and text_extractors/pdf.py extraction branches."""

from dataclasses import dataclass
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.domains.converters.text_extractors.pdf import (
    PageExtractionResult,
    PdfExtractionResult,
    _extract_page,
    text_to_markdown,
)


# ---------------------------------------------------------------------------
# _extract_page — needs_ocr logic
# ---------------------------------------------------------------------------


@dataclass
class PageCase:
    name: str
    text: str
    char_count: int
    has_images: bool
    expected_needs_ocr: bool


PAGE_CASES = [
    PageCase(
        name="enough_text_no_images",
        text="A" * 200,
        char_count=200,
        has_images=False,
        expected_needs_ocr=False,
    ),
    PageCase(
        name="below_min_chars",
        text="Hi",
        char_count=2,
        has_images=False,
        expected_needs_ocr=True,
    ),
    PageCase(
        name="images_with_low_text",
        text="A" * 100,
        char_count=100,
        has_images=True,
        expected_needs_ocr=True,
    ),
    PageCase(
        name="images_with_enough_text",
        text="A" * 300,
        char_count=300,
        has_images=True,
        expected_needs_ocr=False,
    ),
    PageCase(
        name="empty_page",
        text="",
        char_count=0,
        has_images=False,
        expected_needs_ocr=True,
    ),
]


@pytest.mark.parametrize("case", PAGE_CASES, ids=lambda c: c.name)
def test_extract_page_needs_ocr(case: PageCase):
    page = MagicMock()
    page.get_text.return_value = case.text
    page.get_images.return_value = [MagicMock()] if case.has_images else []

    result = _extract_page(page, 0)

    assert result.needs_ocr == case.expected_needs_ocr


def test_extract_page_exception_returns_needs_ocr():
    """If page.get_text raises, the page needs OCR."""
    page = MagicMock()
    page.get_text.side_effect = RuntimeError("corrupted page")

    result = _extract_page(page, 0)

    assert result.needs_ocr is True
    assert result.text == ""


# ---------------------------------------------------------------------------
# PdfExtractionResult properties
# ---------------------------------------------------------------------------


class TestPdfExtractionResult:
    def test_fully_extracted_all_good(self):
        result = PdfExtractionResult(
            path="/test.pdf",
            pages=[
                PageExtractionResult(page_num=0, text="Hello world" * 10, needs_ocr=False),
                PageExtractionResult(page_num=1, text="Page two" * 10, needs_ocr=False),
            ],
        )
        assert result.fully_extracted is True
        assert result.extraction_ratio == 1.0
        assert "Hello world" in result.full_text

    def test_partially_extracted(self):
        result = PdfExtractionResult(
            path="/test.pdf",
            pages=[
                PageExtractionResult(page_num=0, text="Good page", needs_ocr=False),
                PageExtractionResult(page_num=1, text="", needs_ocr=True),
            ],
        )
        assert result.fully_extracted is False
        assert result.extraction_ratio == 0.5
        assert result.pages_needing_ocr == [1]

    def test_empty_pdf(self):
        result = PdfExtractionResult(path="/test.pdf", pages=[])
        assert result.fully_extracted is False
        assert result.extraction_ratio == 0.0
        assert result.full_text == ""


# ---------------------------------------------------------------------------
# text_to_markdown
# ---------------------------------------------------------------------------


class TestTextToMarkdown:
    def test_empty_text(self):
        assert text_to_markdown("") == ""

    def test_plain_text(self):
        result = text_to_markdown("This is a paragraph of normal text.")
        assert "This is a paragraph of normal text." in result

    def test_uppercase_heading(self):
        result = text_to_markdown("INTRODUCTION")
        assert "## Introduction" in result

    def test_bullet_points(self):
        result = text_to_markdown("• Item one\n• Item two")
        assert "- Item one" in result
        assert "- Item two" in result
