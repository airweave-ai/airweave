"""Text converters for converting files to markdown."""

from .code_converter import CodeConverter
from .html_converter import HtmlConverter
from .mistral_converter import MistralConverter
from .txt_converter import TxtConverter
from .xlsx_converter import XlsxConverter

# Singleton instances
mistral_converter = MistralConverter()
html_converter = HtmlConverter()
xlsx_converter = XlsxConverter()  # Local openpyxl extraction (not Mistral)
txt_converter = TxtConverter()
code_converter = CodeConverter()

# Aliases for backward compatibility
pdf_converter = mistral_converter  # PDF uses Mistral OCR
docx_converter = mistral_converter  # DOCX uses Mistral OCR
pptx_converter = mistral_converter  # PPTX uses Mistral OCR
img_converter = mistral_converter  # Images use Mistral OCR

__all__ = [
    "mistral_converter",
    "pdf_converter",
    "docx_converter",
    "img_converter",
    "html_converter",
    "pptx_converter",
    "txt_converter",
    "xlsx_converter",
    "code_converter",
]
