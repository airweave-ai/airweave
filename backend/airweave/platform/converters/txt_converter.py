"""Text file to markdown converter."""

import asyncio
import csv
import json
import os
import xml.dom.minidom
from typing import Dict, List

import aiofiles

from airweave.core.logging import logger
from airweave.platform.converters._base import BaseTextConverter
from airweave.platform.sync.async_helpers import run_in_thread_pool
from airweave.platform.sync.exceptions import EntityProcessingError


class TxtConverter(BaseTextConverter):
    """Converts text files (TXT, CSV, JSON, XML, MD, YAML, TOML) to markdown.

    Features:
    - CSV: Converts to markdown tables
    - JSON: Pretty-prints with code fence
    - XML: Pretty-prints with code fence
    - Others: Returns as plain text
    """

    async def convert_batch(self, file_paths: List[str]) -> Dict[str, str]:
        """Convert text files to markdown.

        Args:
            file_paths: List of text file paths

        Returns:
            Dict mapping file_path -> markdown content (None if failed)
        """
        logger.debug(f"Converting {len(file_paths)} text files to markdown...")

        results = {}
        semaphore = asyncio.Semaphore(20)  # Limit concurrent file reads

        async def _convert_one(path: str):
            async with semaphore:
                try:
                    # Determine format from extension
                    _, ext = os.path.splitext(path)
                    ext = ext.lower()

                    # Dispatch to format-specific handler
                    if ext == ".csv":
                        text = await self._convert_csv(path)
                    elif ext == ".json":
                        text = await self._convert_json(path)
                    elif ext == ".xml":
                        text = await self._convert_xml(path)
                    else:
                        # Plain text (TXT, MD, YAML, TOML, etc.)
                        text = await self._convert_plain_text(path)

                    if text and text.strip():
                        results[path] = text.strip()
                        logger.debug(f"Converted text file: {path} ({len(text)} chars)")
                    else:
                        logger.warning(f"Text file conversion produced no content: {path}")
                        results[path] = None

                except Exception as e:
                    logger.error(f"Text file conversion failed for {path}: {e}")
                    results[path] = None

        await asyncio.gather(*[_convert_one(p) for p in file_paths], return_exceptions=True)

        successful = sum(1 for r in results.values() if r)
        logger.debug(f"Text conversion complete: {successful}/{len(file_paths)} successful")

        return results

    async def _convert_plain_text(self, path: str) -> str:
        """Read plain text file.

        Args:
            path: Path to text file

        Returns:
            File content as string
        """
        async with aiofiles.open(path, "r", encoding="utf-8", errors="ignore") as f:
            return await f.read()

    async def _convert_csv(self, path: str) -> str:
        """Convert CSV to markdown table.

        Args:
            path: Path to CSV file

        Returns:
            Markdown table string

        Raises:
            EntityProcessingError: If CSV is empty
        """

        def _read_and_convert():
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.reader(f)
                rows = list(reader)

            if not rows:
                raise EntityProcessingError(f"CSV file {path} is empty")

            # Create markdown table
            md = []

            # Header
            md.append("| " + " | ".join(rows[0]) + " |")
            md.append("|" + "|".join(["---"] * len(rows[0])) + "|")

            # Data rows
            for row in rows[1:]:
                # Pad if row is shorter than header
                padded = row + [""] * (len(rows[0]) - len(row))
                md.append("| " + " | ".join(padded[: len(rows[0])]) + " |")

            return "\n".join(md)

        return await run_in_thread_pool(_read_and_convert)

    async def _convert_json(self, path: str) -> str:
        """Convert JSON to pretty-printed code fence.

        Args:
            path: Path to JSON file

        Returns:
            Formatted JSON in markdown code fence

        Raises:
            EntityProcessingError: If JSON syntax is invalid
        """

        def _read_and_format():
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)

            formatted = json.dumps(data, indent=2)
            return f"```json\n{formatted}\n```"

        try:
            return await run_in_thread_pool(_read_and_format)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {path}: {e}")
            raise EntityProcessingError(f"Invalid JSON syntax in {path}")

    async def _convert_xml(self, path: str) -> str:
        """Convert XML to pretty-printed code fence.

        Args:
            path: Path to XML file

        Returns:
            Formatted XML in markdown code fence
        """

        def _read_and_format():
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            dom = xml.dom.minidom.parseString(content)
            formatted = dom.toprettyxml()
            return f"```xml\n{formatted}\n```"

        try:
            return await run_in_thread_pool(_read_and_format)
        except Exception as e:
            logger.warning(f"XML parsing failed for {path}: {e}, using raw content")
            # Fallback to raw content
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                raw = f.read()
            return f"```xml\n{raw}\n```" if raw.strip() else None
