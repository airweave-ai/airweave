"""Text converters for converting files and URLs to markdown.

Singleton converter instances are created lazily (on first attribute access).
OCR is pulled from the DI container — the container is guaranteed to be
initialized before any sync runs (startup in main.py / worker.py).
"""

import sys

from .code_converter import CodeConverter
from .docx_converter import DocxConverter
from .html_converter import HtmlConverter
from .pdf_converter import PdfConverter
from .pptx_converter import PptxConverter
from .txt_converter import TxtConverter
from .web_converter import WebConverter
from .xlsx_converter import XlsxConverter

# ---------------------------------------------------------------------------
# Lazy singleton initialisation
# ---------------------------------------------------------------------------
#
# ``from .pdf_converter import PdfConverter`` also adds the *module*
# ``pdf_converter`` as an attribute of this package.  That shadows the lazy
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


def _init_singletons() -> dict:
    """Create all converter singletons (called once, on first access).

    OCR is pulled from the DI container (``container.ocr_provider``)
    which provides a FallbackOcrProvider with circuit breaking built in.
    """
    global _singletons
    if _singletons is not None:
        return _singletons

    from airweave.core.container import container

    ocr = container.ocr_provider

    _singletons = {
        "mistral_converter": ocr,
        "pdf_converter": PdfConverter(ocr_provider=ocr),
        "docx_converter": DocxConverter(ocr_provider=ocr),
        "pptx_converter": PptxConverter(ocr_provider=ocr),
        "img_converter": ocr,  # Images go directly to OCR
        "html_converter": HtmlConverter(),
        "txt_converter": TxtConverter(),
        "xlsx_converter": XlsxConverter(),  # Local openpyxl
        "code_converter": CodeConverter(),
        "web_converter": WebConverter(),  # URL fetching → HTML → markdown
    }

    # Also set as module attributes so subsequent lookups are O(1)
    # (bypasses __getattr__ after first access).
    this_module = sys.modules[__name__]
    for _name, _value in _singletons.items():
        setattr(this_module, _name, _value)

    return _singletons


def __getattr__(name: str):
    """PEP 562 module-level ``__getattr__`` for lazy singleton access."""
    if name in _SINGLETON_NAMES:
        return _init_singletons()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = sorted(_SINGLETON_NAMES)
