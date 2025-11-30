"""Text converters for converting files and URLs to markdown."""

from .code_converter import CodeConverter
from .html_converter import HtmlConverter
from .markitdown_converter import MarkItDownConverter
from .mistral_converter import MistralConverter
from .txt_converter import TxtConverter
from .web_converter import WebConverter
from .xlsx_converter import XlsxConverter

# Singleton instances
mistral_converter = MistralConverter()
markitdown_converter = MarkItDownConverter()
html_converter = HtmlConverter()
xlsx_converter = XlsxConverter()  # Local openpyxl extraction (not Mistral)
txt_converter = TxtConverter()
code_converter = CodeConverter()
web_converter = WebConverter()  # URL fetching and HTML to markdown

# Aliases for backward compatibility
# Use MarkItDown (local) instead of Mistral (cloud)
pdf_converter = markitdown_converter
docx_converter = markitdown_converter
pptx_converter = markitdown_converter
img_converter = markitdown_converter

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
    "web_converter",
]
