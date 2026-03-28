"""Tests for DocConverter — _try_extract success and failure paths."""

from unittest.mock import AsyncMock, patch

import pytest

from airweave.domains.converters.doc import DocConverter


@pytest.fixture
def converter():
    return DocConverter(ocr_provider=None)


class TestDocConverter:

    @pytest.mark.asyncio
    async def test_try_extract_success(self, converter):
        """When extract_doc_text returns content, _try_extract returns it."""
        with patch(
            "airweave.domains.converters.doc.extract_doc_text",
            new_callable=AsyncMock,
            return_value="Hello world document content",
        ):
            result = await converter._try_extract("/fake/doc.doc")

        assert result == "Hello world document content"

    @pytest.mark.asyncio
    async def test_try_extract_returns_none(self, converter):
        """When extract_doc_text returns None, _try_extract returns None (needs OCR)."""
        with patch(
            "airweave.domains.converters.doc.extract_doc_text",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await converter._try_extract("/fake/doc.doc")

        assert result is None

    @pytest.mark.asyncio
    async def test_try_extract_empty_string(self, converter):
        """Empty string from extractor is returned as-is (treated as falsy by convert_batch)."""
        with patch(
            "airweave.domains.converters.doc.extract_doc_text",
            new_callable=AsyncMock,
            return_value="",
        ):
            result = await converter._try_extract("/fake/doc.doc")

        assert result == ""
