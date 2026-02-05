"""Text converters for converting files and URLs to markdown.

Singleton converter instances are created lazily (on first attribute access)
to avoid a circular import between this package and ``airweave.platform.ocr``.
The OCR package's ``MistralOCR`` imports from ``converters._base``, so
eagerly importing it here would re-enter the ``converters`` package before
``_base`` has been loaded.
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

# TODO: Move all of this to specialized DI container

# ---------------------------------------------------------------------------
# Lazy singleton initialisation (avoids circular import with platform.ocr)
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
    """Create all converter singletons (called once, on first access)."""
    global _singletons
    if _singletons is not None:
        return _singletons

    # Deferred import — safe now because _base is already loaded.
    from airweave.platform.ocr import MistralOCR

    _mistral = MistralOCR()  # Pure OCR (no text extraction)

    _singletons = {
        "mistral_converter": _mistral,
        "pdf_converter": PdfConverter(ocr_provider=_mistral),
        "docx_converter": DocxConverter(ocr_provider=_mistral),
        "pptx_converter": PptxConverter(ocr_provider=_mistral),
        "img_converter": _mistral,  # Images go directly to OCR
        "html_converter": HtmlConverter(),
        "txt_converter": TxtConverter(),
        "xlsx_converter": XlsxConverter(),  # Local openpyxl (not Mistral)
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
