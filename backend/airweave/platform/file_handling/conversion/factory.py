"""Factory for document converters.

Handles selecting the appropriate converter for different file types.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

from airweave.core.logging import logger
from airweave.platform.file_handling.conversion._base import (
    DocumentConverter,
    DocumentConverterResult,
)
from airweave.platform.file_handling.conversion.converters.docx_converter import DocxConverter
from airweave.platform.file_handling.conversion.converters.html_converter import HtmlConverter
from airweave.platform.file_handling.conversion.converters.img_converter import AsyncImageConverter
from airweave.platform.file_handling.conversion.converters.pdf_converter import PdfConverter
from airweave.platform.file_handling.conversion.converters.pptx_converter import PptxConverter
from airweave.platform.file_handling.conversion.converters.txt_converter import TextConverter
from airweave.platform.file_handling.conversion.converters.xlsx_converter import XlsxConverter


class DocumentConverterFactory:
    """Factory class for creating and managing document converters."""

    SUPPORTED_EXTENSIONS = {
        # Image files
        ".jpg": "image",
        ".jpeg": "image",
        ".png": "image",
        # PDF files
        ".pdf": "pdf",
        # Office document files
        ".docx": "docx",
        ".pptx": "pptx",
        ".xlsx": "xlsx",
        # Web files
        ".html": "html",
        ".htm": "html",
        # Text files
        ".txt": "text",
        ".csv": "text",
        ".json": "text",
        ".xml": "text",
    }

    def __init__(self, llm_client: Optional[Any] = None, llm_model: Optional[str] = None):
        """Initialize the factory with optional LLM client and model.

        Args:
            llm_client: Optional LLM client for converters that need it
            llm_model: Optional LLM model name for converters that need it
        """
        self._llm_client = llm_client
        self._llm_model = llm_model
        self._converters: Dict[str, DocumentConverter] = {}
        self._initialize_converters()

    def _initialize_converters(self) -> None:
        """Initialize all available converters."""
        # Initialize image converter
        image_converter = AsyncImageConverter()
        self._converters["image"] = image_converter

        # Initialize PDF converter
        pdf_converter = PdfConverter()
        self._converters["pdf"] = pdf_converter

        # Initialize Office document converters
        docx_converter = DocxConverter()
        self._converters["docx"] = docx_converter

        pptx_converter = PptxConverter()
        self._converters["pptx"] = pptx_converter

        xlsx_converter = XlsxConverter()
        self._converters["xlsx"] = xlsx_converter

        # Initialize web file converters
        html_converter = HtmlConverter()
        self._converters["html"] = html_converter

        # Initialize text file converters
        text_converter = TextConverter()
        self._converters["text"] = text_converter

    def get_converter(self, file_path: str) -> Optional[DocumentConverter]:
        """Get the appropriate converter for a file based on its extension.

        Args:
            file_path: Path to the file

        Returns:
            DocumentConverter instance or None if not supported
        """
        _, extension = os.path.splitext(file_path)
        extension = extension.lower()

        converter_type = self.SUPPORTED_EXTENSIONS.get(extension)
        if not converter_type:
            return None

        return self._converters.get(converter_type)

    async def convert(self, file_path: str, **kwargs: Any) -> Union[None, DocumentConverterResult]:
        """Convert a file to markdown using the appropriate converter.

        Args:
            file_path: Path to the file to convert
            **kwargs: Additional arguments to pass to the converter

        Returns:
            DocumentConverterResult or None if conversion fails

        Raises:
            ValueError: If file type is not supported or file doesn't exist
        """
        if not os.path.exists(file_path):
            raise ValueError(f"File not found: {file_path}")

        # Get file extension
        _, extension = os.path.splitext(file_path)
        if not extension:
            raise ValueError("File must have an extension")

        extension = extension.lower()
        if extension not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {extension}")

        # Get the appropriate converter
        converter = self.get_converter(file_path)
        if not converter:
            raise ValueError(f"No converter found for file type: {extension}")

        # Add default kwargs
        if "file_extension" not in kwargs:
            kwargs["file_extension"] = extension
        if "llm_client" not in kwargs and self._llm_client:
            kwargs["llm_client"] = self._llm_client
        if "llm_model" not in kwargs and self._llm_model:
            kwargs["llm_model"] = self._llm_model

        try:
            result = await converter.convert(file_path, **kwargs)
            return result
        except Exception as e:
            logger.error(f"Error converting file {file_path}: {str(e)}")
            return None

    def is_supported(self, file_path: str) -> bool:
        """Check if the file extension is supported.

        Args:
            file_path: Path to the file

        Returns:
            True if supported, False otherwise
        """
        ext = Path(file_path).suffix.lower()
        return ext in self.SUPPORTED_EXTENSIONS


# Create singleton instance - without hard-coded clients
document_converter = DocumentConverterFactory()
