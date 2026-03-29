"""Tests for ConverterRegistry."""

from unittest.mock import AsyncMock

from airweave.domains.converters._base import BaseTextConverter, OcrConverterAdapter
from airweave.domains.converters.code import CodeConverter
from airweave.domains.converters.doc import DocConverter
from airweave.domains.converters.html import HtmlConverter
from airweave.domains.converters.pdf import PdfConverter
from airweave.domains.converters.registry import ConverterRegistry
from airweave.domains.converters.txt import TxtConverter
from airweave.domains.converters.web import WebConverter
from airweave.domains.converters.xlsx import XlsxConverter


class TestConverterRegistry:
    def test_builds_without_ocr(self):
        registry = ConverterRegistry(ocr_provider=None)
        assert registry.for_extension(".pdf") is not None
        assert isinstance(registry.for_extension(".pdf"), PdfConverter)

    def test_extension_mapping(self):
        registry = ConverterRegistry(ocr_provider=None)
        assert isinstance(registry.for_extension(".doc"), DocConverter)
        assert isinstance(registry.for_extension(".html"), HtmlConverter)
        assert isinstance(registry.for_extension(".txt"), TxtConverter)
        assert isinstance(registry.for_extension(".xlsx"), XlsxConverter)
        assert isinstance(registry.for_extension(".py"), CodeConverter)

    def test_unknown_extension_returns_none(self):
        registry = ConverterRegistry(ocr_provider=None)
        assert registry.for_extension(".unknown") is None

    def test_for_web_returns_web_converter(self):
        registry = ConverterRegistry(ocr_provider=None)
        assert isinstance(registry.for_web(), WebConverter)

    def test_image_extensions_absent_without_ocr(self):
        registry = ConverterRegistry(ocr_provider=None)
        assert registry.for_extension(".jpg") is None
        assert registry.for_extension(".jpeg") is None
        assert registry.for_extension(".png") is None

    def test_image_extensions_return_adapter_with_ocr(self):
        mock_ocr = AsyncMock()
        mock_ocr.convert_batch = AsyncMock(return_value={})
        registry = ConverterRegistry(ocr_provider=mock_ocr)

        for ext in (".jpg", ".jpeg", ".png"):
            converter = registry.for_extension(ext)
            assert converter is not None, f"{ext} should have a converter"
            assert isinstance(converter, BaseTextConverter), f"{ext} converter should be BaseTextConverter"
            assert isinstance(converter, OcrConverterAdapter), f"{ext} converter should be OcrConverterAdapter"
