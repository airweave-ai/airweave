"""OCR provider implementations.

Re-exports :class:`MistralOCR` so consumers can do::

    from airweave.platform.ocr import MistralOCR
"""

from airweave.platform.ocr.mistral.converter import MistralOCR

__all__ = ["MistralOCR"]
