"""OCR adapters."""

from airweave.adapters.ocr.fake import FakeOcrProvider
from airweave.adapters.ocr.mistral import MistralOcrAdapter

__all__ = ["MistralOcrAdapter", "FakeOcrProvider"]
