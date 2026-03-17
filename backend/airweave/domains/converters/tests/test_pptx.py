"""Tests for PptxConverter — _try_extract success and failure paths."""

from unittest.mock import AsyncMock, patch

import pytest

from airweave.domains.converters.pptx import PptxConverter


@pytest.fixture
def converter():
    return PptxConverter(ocr_provider=None)


class TestPptxConverter:

    @pytest.mark.asyncio
    async def test_try_extract_success(self, converter):
        """When extract_pptx_text returns content, _try_extract returns it."""
        with patch(
            "airweave.domains.converters.pptx.extract_pptx_text",
            new_callable=AsyncMock,
            return_value="# Slide 1\n\nBullet point",
        ):
            result = await converter._try_extract("/fake/pres.pptx")

        assert result == "# Slide 1\n\nBullet point"

    @pytest.mark.asyncio
    async def test_try_extract_returns_none(self, converter):
        """When extract_pptx_text returns None, _try_extract returns None (needs OCR)."""
        with patch(
            "airweave.domains.converters.pptx.extract_pptx_text",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await converter._try_extract("/fake/pres.pptx")

        assert result is None
