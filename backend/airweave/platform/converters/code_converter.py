"""Code file to markdown converter."""

import asyncio
from typing import Dict, List

import aiofiles

from airweave.core.logging import logger
from airweave.platform.converters._base import BaseTextConverter


class CodeConverter(BaseTextConverter):
    """Converts code files to markdown code fences.

    Simple converter that wraps code content in markdown code fences
    with appropriate language tags. No AI summarization - code-specific
    embeddings will be used later for optimal retrieval.
    """

    async def convert_batch(self, file_paths: List[str]) -> Dict[str, str]:
        """Convert code files to markdown code fences.

        Args:
            file_paths: List of code file paths

        Returns:
            Dict mapping file_path -> markdown (code fence with language tag)
        """
        logger.debug(f"Converting {len(file_paths)} code files to markdown...")

        results = {}
        semaphore = asyncio.Semaphore(20)  # Limit concurrent file reads

        async def _convert_one(path: str):
            async with semaphore:
                try:
                    # Read file
                    async with aiofiles.open(path, "r", encoding="utf-8", errors="ignore") as f:
                        code = await f.read()

                    if not code or not code.strip():
                        logger.warning(f"Code file {path} is empty")
                        results[path] = None
                        return

                    # Return raw code (no fence - CodeChunker uses auto-detection)
                    results[path] = code
                    logger.debug(f"Converted code file: {path} ({len(code)} characters)")

                except Exception as e:
                    logger.error(f"Failed to process code file {path}: {e}")
                    results[path] = None

        await asyncio.gather(*[_convert_one(p) for p in file_paths], return_exceptions=True)

        successful = sum(1 for r in results.values() if r)
        logger.debug(f"Code conversion complete: {successful}/{len(file_paths)} successful")

        return results
