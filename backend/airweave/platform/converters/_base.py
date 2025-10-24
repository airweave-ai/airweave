"""Base converter interface for text converters."""

from abc import ABC, abstractmethod
from typing import Dict, List


class BaseTextConverter(ABC):
    """Base class for all text converters."""

    @abstractmethod
    async def convert_batch(self, file_paths: List[str]) -> Dict[str, str]:
        """Batch convert files to markdown text.

        Args:
            file_paths: List of file paths to convert

        Returns:
            Dict mapping file_path -> markdown text content
        """
        pass
