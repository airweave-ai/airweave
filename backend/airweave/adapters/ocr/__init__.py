"""OCR adapters."""

from airweave.adapters.ocr.docling import DoclingOcrAdapter
from airweave.adapters.ocr.fake import FakeOcrProvider
from airweave.adapters.ocr.fallback import FallbackOcrProvider
from airweave.adapters.ocr.mistral import MistralOcrAdapter

__all__ = [
    "DoclingOcrAdapter",
    "FakeOcrProvider",
    "FallbackOcrProvider",
    "MistralOcrAdapter",
]
