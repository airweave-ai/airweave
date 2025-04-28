"""Base classes and interfaces for document conversion."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Set, Union


class DocumentConverterResult:
    """The result of converting a document to text."""

    def __init__(
        self,
        title: Optional[str] = None,
        text_content: str = "",
        file_path: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the AsyncDocumentConverterResult.

        Args:
            title: The document title if available
            text_content: The extracted text content in markdown format
            file_path: The path to the original file
            metadata: Additional metadata extracted from the document
        """
        self.title: Optional[str] = title
        self.text_content: str = text_content
        self.file_path: str = file_path
        self.metadata: Dict[str, Any] = metadata or {}


class DocumentConverter(ABC):
    """Abstract base class for all document converters."""

    @abstractmethod
    async def convert(self, local_path: str, **kwargs: Any) -> Union[None, DocumentConverterResult]:
        """Convert a document to markdown text.

        Args:
            local_path: Path to the document file
            **kwargs: Additional arguments for the conversion process
                file_extension: The file extension of the document
                llm_client: Optional LLM client for enhanced conversion
                llm_model: Optional LLM model identifier
                llm_prompt: Optional prompt for LLM

        Returns:
            AsyncDocumentConverterResult containing the markdown text,
            or None if this converter doesn't support the file type
        """
        pass


class DocumentFactory(ABC):
    """Factory interface for selecting the appropriate document converter."""

    SUPPORTED_EXTENSIONS: Set[str] = set()

    @abstractmethod
    def __init__(self, **kwargs: Any):
        """Initialize the factory with optional configuration."""
        pass

    @abstractmethod
    async def convert(self, file_path: str, **kwargs: Any) -> DocumentConverterResult:
        """Convert a document to markdown using the appropriate converter.

        Args:
            file_path: Path to the document file
            **kwargs: Additional arguments for the conversion process

        Returns:
            AsyncDocumentConverterResult containing the markdown text

        Raises:
            ValueError: If no suitable converter is found or the file type is unsupported
            FileNotFoundError: If the file doesn't exist
        """
        pass

    @abstractmethod
    def _is_supported(self, file_path: str) -> bool:
        """Check if the file extension is supported.

        Args:
            file_path: Path to the document file

        Returns:
            True if the file extension is supported, False otherwise
        """
        pass
