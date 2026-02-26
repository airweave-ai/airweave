"""Tests for initialize_converters with optional OCR provider."""

import airweave.platform.converters as converters_mod
from airweave.adapters.ocr.fake import FakeOcrProvider
from airweave.platform.converters import PdfConverter, initialize_converters


class TestInitializeConverters:
    def setup_method(self):
        """Reset singleton state before each test."""
        converters_mod._singletons = None

    def teardown_method(self):
        """Clean up singleton state after each test."""
        converters_mod._singletons = None

    def test_accepts_none_ocr_provider(self):
        """When OCR is None, document converters work without OCR."""
        initialize_converters(None)

        assert converters_mod._singletons is not None
        assert converters_mod._singletons["mistral_converter"] is None
        assert converters_mod._singletons["img_converter"] is None
        assert isinstance(converters_mod._singletons["pdf_converter"], PdfConverter)

    def test_accepts_fake_ocr_provider(self):
        """When OCR is provided, it is wired into document converters."""
        fake = FakeOcrProvider()
        initialize_converters(fake)

        assert converters_mod._singletons is not None
        assert converters_mod._singletons["mistral_converter"] is fake
        assert converters_mod._singletons["img_converter"] is fake
