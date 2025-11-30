"""Converter for documents and images using MarkItDown (Local)."""

from typing import Dict, List, Optional

from airweave.core.logging import logger
from airweave.platform.converters._base import BaseTextConverter
from airweave.platform.sync.async_helpers import run_in_thread_pool
from airweave.platform.sync.exceptions import EntityProcessingError, SyncFailureError


class MarkItDownConverter(BaseTextConverter):
    """Converts documents and images to markdown using MarkItDown (Local).
    
    Supported formats:
    - Documents: PDF, DOCX, PPTX, XLSX
    - Images: JPG, JPEG, PNG
    """

    def __init__(self):
        """Initialize converter with optional OpenAI support."""
        try:
            from markitdown import MarkItDown
            from airweave.core.config import settings
            
            llm_client = None
            llm_model = None
            
            if hasattr(settings, "OPENAI_API_KEY") and settings.OPENAI_API_KEY:
                try:
                    from openai import OpenAI
                    llm_client = OpenAI(api_key=settings.OPENAI_API_KEY)
                    llm_model = "gpt-4o"
                    logger.info("MarkItDown initialized with OpenAI (gpt-4o) support")
                except ImportError:
                    logger.warning("openai package not found, falling back to basic MarkItDown")
                except Exception as e:
                    logger.warning(f"Failed to initialize OpenAI client: {e}")

            self._md = MarkItDown(llm_client=llm_client, llm_model=llm_model)
            if not llm_client:
                logger.info("MarkItDown initialized in basic mode (local only)")
                
        except ImportError:
            logger.error("markitdown package not found")
            self._md = None

    async def convert_batch(self, file_paths: List[str]) -> Dict[str, str]:
        """Convert document files to markdown text using MarkItDown.

        Args:
            file_paths: List of document file paths to convert

        Returns:
            Dict mapping file_path -> markdown text content (None if failed)
        """
        if not self._md:
             raise SyncFailureError("markitdown package required but not installed")

        results = {}
        
        # Process files sequentially (MarkItDown might not be thread-safe or CPU bound)
        # We can try parallelizing if needed, but for now safe sequential in thread pool
        for path in file_paths:
            try:
                text = await self._convert_single(path)
                results[path] = text
            except Exception as e:
                logger.error(f"Failed to convert {path} with MarkItDown: {e}")
                results[path] = None
                
        return results

    async def _convert_single(self, file_path: str) -> str:
        """Convert a single file."""
        def _convert():
            result = self._md.convert(file_path)
            return result.text_content

        return await run_in_thread_pool(_convert)
