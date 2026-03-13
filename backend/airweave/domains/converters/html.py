"""HTML to markdown converter."""

import asyncio
from typing import Dict, List

from airweave.core.logging import logger
from airweave.domains.converters._base import BaseTextConverter
from airweave.domains.sync_pipeline.async_helpers import run_in_thread_pool
from airweave.domains.sync_pipeline.exceptions import EntityProcessingError


class HtmlConverter(BaseTextConverter):
    """Converts HTML files to markdown text using html-to-markdown."""

    async def convert_batch(self, file_paths: List[str]) -> Dict[str, str]:
        """Convert HTML files to markdown text."""
        try:
            from html_to_markdown import convert
        except ImportError:
            logger.error("html-to-markdown package not installed for HTML conversion")
            raise EntityProcessingError(
                "HTML conversion requires html-to-markdown package. "
                "Install with: pip install html-to-markdown"
            )

        logger.info(f"Converting {len(file_paths)} HTML files to markdown...")

        results = {}
        semaphore = asyncio.Semaphore(20)

        async def _convert_one(path: str):
            async with semaphore:
                try:

                    def _convert():
                        with open(path, "rb") as f:
                            raw_bytes = f.read()

                        if not raw_bytes:
                            return None

                        try:
                            html_content = raw_bytes.decode("utf-8")
                        except UnicodeDecodeError:
                            html_content = raw_bytes.decode("utf-8", errors="replace")
                            replacement_count = html_content.count("\ufffd")
                            if replacement_count > 100:
                                raise EntityProcessingError(
                                    f"HTML contains excessive binary data "
                                    f"({replacement_count} replacement chars)"
                                )

                        if not html_content.strip():
                            return None

                        markdown = convert(html_content)

                        return markdown.strip() if markdown else None

                    text = await run_in_thread_pool(_convert)

                    if text:
                        results[path] = text
                        logger.debug(f"Converted HTML file: {path} ({len(text)} characters)")
                    else:
                        logger.warning(f"HTML conversion produced no content for {path}")
                        results[path] = None

                except Exception as e:
                    logger.error(f"HTML conversion failed for {path}: {e}")
                    results[path] = None

        await asyncio.gather(*[_convert_one(p) for p in file_paths], return_exceptions=True)

        successful = sum(1 for r in results.values() if r)
        logger.info(f"HTML conversion complete: {successful}/{len(file_paths)} files successful")

        return results
