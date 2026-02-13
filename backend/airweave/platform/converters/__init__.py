"""Text converters for converting files and URLs to markdown.

Converter singletons are initialized explicitly at startup via
``initialize_converters()``. OCR is injected as a parameter — the
converters module never imports the DI container.
"""

import sys
from typing import TYPE_CHECKING

from .code_converter import CodeConverter
from .docx_converter import DocxConverter
from .html_converter import HtmlConverter
from .pdf_converter import PdfConverter
from .pptx_converter import PptxConverter
from .txt_converter import TxtConverter
from .web_converter import WebConverter
from .xlsx_converter import XlsxConverter

if TYPE_CHECKING:
    from airweave.core.protocols import OcrProvider

# ---------------------------------------------------------------------------
# Singleton management
# ---------------------------------------------------------------------------
#
# ``from .pdf_converter import PdfConverter`` also adds the *module*
# ``pdf_converter`` as an attribute of this package.  That shadows the
# singleton of the same name and prevents ``__getattr__`` from firing.
# Remove the module references so the singleton lookup works correctly.
# (The submodules remain in ``sys.modules`` so direct imports still work.)

_SINGLETON_NAMES = frozenset(
    {
        "mistral_converter",
        "pdf_converter",
        "docx_converter",
        "pptx_converter",
        "img_converter",
        "html_converter",
        "txt_converter",
        "xlsx_converter",
        "code_converter",
        "web_converter",
    }
)

for _mod in (
    "code_converter",
    "docx_converter",
    "html_converter",
    "pdf_converter",
    "pptx_converter",
    "txt_converter",
    "web_converter",
    "xlsx_converter",
):
    vars().pop(_mod, None)
del _mod

_singletons: dict | None = None


def initialize_converters(ocr_provider: "OcrProvider") -> None:
    """Initialize converter singletons with the given OCR provider.

    Called once at startup from ``main.py`` lifespan and ``worker main()``.
    The OCR provider is passed explicitly — no container import needed.

    Args:
        ocr_provider: The OCR provider (e.g., FallbackOcrProvider with
            circuit breaking) to inject into document converters.
    """
    global _singletons
    if _singletons is not None:
        return

    _singletons = {
        "mistral_converter": ocr_provider,
        "pdf_converter": PdfConverter(ocr_provider=ocr_provider),
        "docx_converter": DocxConverter(ocr_provider=ocr_provider),
        "pptx_converter": PptxConverter(ocr_provider=ocr_provider),
        "img_converter": ocr_provider,  # Images go directly to OCR
        "html_converter": HtmlConverter(),
        "txt_converter": TxtConverter(),
        "xlsx_converter": XlsxConverter(),
        "code_converter": CodeConverter(),
        "web_converter": WebConverter(),
    }

    # Also set as module attributes so subsequent lookups are O(1)
    # (bypasses __getattr__ after first access).
    this_module = sys.modules[__name__]
    for _name, _value in _singletons.items():
        setattr(this_module, _name, _value)


def __getattr__(name: str):
    """PEP 562 module-level ``__getattr__`` for singleton access."""
    if name in _SINGLETON_NAMES:
        if _singletons is None:
            raise RuntimeError(
                "Converters not initialized. Call initialize_converters() at startup."
            )
        return _singletons[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = sorted(_SINGLETON_NAMES)
