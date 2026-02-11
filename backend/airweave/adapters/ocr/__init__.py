"""OCR adapters."""

from airweave.adapters.ocr.fake import FakeOcrProvider
from airweave.adapters.ocr.fallback import FallbackOcrProvider
from airweave.adapters.ocr.google_document_ai import GoogleDocumentAIOcrAdapter
from airweave.adapters.ocr.mistral import MistralOcrAdapter

__all__ = [
    "MistralOcrAdapter",
    "GoogleDocumentAIOcrAdapter",
    "FallbackOcrProvider",
    "FakeOcrProvider",
]
