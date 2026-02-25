"""Tests for _create_ocr_provider in the container factory."""

import types
from unittest.mock import patch

import pytest

from airweave.adapters.circuit_breaker.fake import FakeCircuitBreaker
from airweave.adapters.ocr.fake import FakeOcrProvider
from airweave.adapters.ocr.fallback import FallbackOcrProvider
from airweave.core.container.factory import _create_ocr_provider


def _make_settings(docling_base_url=None):
    """Return a minimal namespace with the attrs _create_ocr_provider reads."""
    return types.SimpleNamespace(DOCLING_BASE_URL=docling_base_url)


class TestCreateOcrProvider:
    def test_returns_none_when_no_providers(self):
        """Both Mistral and Docling unavailable -> None."""
        cb = FakeCircuitBreaker()
        settings = _make_settings(docling_base_url=None)

        with patch(
            "airweave.core.container.factory.MistralOcrAdapter",
            side_effect=RuntimeError("no key"),
        ):
            result = _create_ocr_provider(cb, settings)

        assert result is None

    def test_returns_fallback_with_mistral_only(self):
        """Mistral available, no Docling -> FallbackOcrProvider."""
        cb = FakeCircuitBreaker()
        settings = _make_settings(docling_base_url=None)

        with patch(
            "airweave.core.container.factory.MistralOcrAdapter",
            return_value=FakeOcrProvider(),
        ):
            result = _create_ocr_provider(cb, settings)

        assert isinstance(result, FallbackOcrProvider)

    def test_returns_fallback_with_both_providers(self):
        """Both Mistral and Docling available -> FallbackOcrProvider."""
        cb = FakeCircuitBreaker()
        settings = _make_settings(docling_base_url="http://localhost:5001")

        with (
            patch(
                "airweave.core.container.factory.MistralOcrAdapter",
                return_value=FakeOcrProvider(),
            ),
            patch(
                "airweave.core.container.factory.DoclingOcrAdapter",
                return_value=FakeOcrProvider(),
            ),
        ):
            result = _create_ocr_provider(cb, settings)

        assert isinstance(result, FallbackOcrProvider)
