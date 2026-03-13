"""Code file to markdown converter."""

import asyncio
from typing import Dict, List

import aiofiles

from airweave.core.logging import logger
from airweave.domains.converters._base import BaseTextConverter


class CodeConverter(BaseTextConverter):
    """Converts code files to markdown code fences."""

    async def convert_batch(self, file_paths: List[str]) -> Dict[str, str]:
        """Convert code files to markdown code fences."""
        logger.debug(f"Converting {len(file_paths)} code files to markdown...")

        results = {}
        semaphore = asyncio.Semaphore(20)

        async def _convert_one(path: str):
            async with semaphore:
                try:
                    async with aiofiles.open(path, "rb") as f:
                        raw_bytes = await f.read()

                    if not raw_bytes:
                        logger.warning(f"Code file {path} is empty")
                        results[path] = None
                        return

                    try:
                        code = raw_bytes.decode("utf-8")
                        if "\ufffd" not in code:
                            results[path] = code
                            logger.debug(f"Converted code file: {path} ({len(code)} characters)")
                            return
                    except UnicodeDecodeError:
                        pass

                    code = raw_bytes.decode("utf-8", errors="replace")
                    replacement_count = code.count("\ufffd")

                    if replacement_count > 0:
                        logger.warning(
                            f"Code file {path} contains {replacement_count} "
                            f"replacement characters - may be binary data"
                        )
                        results[path] = None
                        return

                    if not code.strip():
                        logger.warning(f"Code file {path} produced no content after decoding")
                        results[path] = None
                        return

                    results[path] = code
                    logger.debug(f"Converted code file: {path} ({len(code)} characters)")

                except Exception as e:
                    logger.error(f"Failed to process code file {path}: {e}")
                    results[path] = None

        await asyncio.gather(*[_convert_one(p) for p in file_paths], return_exceptions=True)

        successful = sum(1 for r in results.values() if r)
        logger.debug(f"Code conversion complete: {successful}/{len(file_paths)} successful")

        return results
