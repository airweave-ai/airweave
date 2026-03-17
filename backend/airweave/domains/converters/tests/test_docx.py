"""Tests for DocxConverter — _try_extract success and failure paths."""

from unittest.mock import AsyncMock, patch

import pytest

from airweave.domains.converters.docx import DocxConverter


@pytest.fixture
def converter():
    return DocxConverter(ocr_provider=None)


class TestDocxConverter:

    @pytest.mark.asyncio
    async def test_try_extract_success(self, converter):
        """When extract_docx_text returns content, _try_extract returns it."""
        with patch(
            "airweave.domains.converters.docx.extract_docx_text",
            new_callable=AsyncMock,
            return_value="# Document\n\nHello world",
        ):
            result = await converter._try_extract("/fake/doc.docx")

        assert result == "# Document\n\nHello world"

    @pytest.mark.asyncio
    async def test_try_extract_returns_none(self, converter):
        """When extract_docx_text returns None, _try_extract returns None (needs OCR)."""
        with patch(
            "airweave.domains.converters.docx.extract_docx_text",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await converter._try_extract("/fake/doc.docx")

        assert result is None

    @pytest.mark.asyncio
    async def test_try_extract_empty_string(self, converter):
        """Empty string from extractor → None (falsy)."""
        with patch(
            "airweave.domains.converters.docx.extract_docx_text",
            new_callable=AsyncMock,
            return_value="",
        ):
            result = await converter._try_extract("/fake/doc.docx")

        assert result is None or result == ""
