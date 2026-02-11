"""Text file to markdown converter."""

import asyncio
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
    """Converts text files (TXT, JSON, XML, MD, YAML, TOML) to markdown.

    Features:
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
                    if ext == ".json":
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
        """Read plain text file with encoding detection.

        Args:
            path: Path to text file

        Returns:
            File content as string

        Raises:
            EntityProcessingError: If file contains excessive binary/corrupted data
        """
        # Read raw bytes for encoding detection
        async with aiofiles.open(path, "rb") as f:
            raw_bytes = await f.read()

        if not raw_bytes:
            return ""

        # Try UTF-8 first (most common)
        try:
            text = raw_bytes.decode("utf-8")
            replacement_count = text.count("\ufffd")
            if replacement_count == 0:
                return text
        except UnicodeDecodeError:
            pass

        # Try encoding detection
        try:
            import chardet

            detection = chardet.detect(raw_bytes[:100000])  # Sample first 100KB
            if detection and detection.get("confidence", 0) > 0.7:
                detected_encoding = detection["encoding"]
                if detected_encoding:
                    try:
                        text = raw_bytes.decode(detected_encoding)
                        replacement_count = text.count("\ufffd")
                        if replacement_count == 0:
                            logger.debug(
                                f"Detected encoding {detected_encoding} for {os.path.basename(path)}"
                            )
                            return text
                    except (UnicodeDecodeError, LookupError):
                        pass
        except ImportError:
            logger.debug("chardet not available, falling back to UTF-8 with ignore")

        # Fallback: decode with replace to create U+FFFD for validation
        text = raw_bytes.decode("utf-8", errors="replace")
        replacement_count = text.count("\ufffd")

        if replacement_count > 0:
            text_length = len(text)
            replacement_ratio = replacement_count / text_length if text_length > 0 else 0

            # Warn if high replacement ratio
            if replacement_ratio > 0.25 or replacement_count > 5000:
                logger.warning(
                    f"File {os.path.basename(path)} contains {replacement_count} "
                    f"replacement characters ({replacement_ratio:.1%}). "
                    f"This may indicate binary data or encoding issues."
                )
                raise EntityProcessingError(
                    f"Text file contains excessive binary/corrupted data: "
                    f"{replacement_count} replacement chars ({replacement_ratio:.1%})"
                )

        return text

    async def _convert_json(self, path: str) -> str:
        """Convert JSON to pretty-printed code fence.

        Args:
            path: Path to JSON file

        Returns:
            Formatted JSON in markdown code fence

        Raises:
            EntityProcessingError: If JSON syntax is invalid or contains corrupted data
        """

        def _read_and_format():
            # Read raw bytes
            with open(path, "rb") as f:
                raw_bytes = f.read()

            # Try UTF-8 first
            try:
                text = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                # Fallback with replace to detect corruption
                text = raw_bytes.decode("utf-8", errors="replace")
                replacement_count = text.count("\ufffd")
                if replacement_count > 50:  # Strict for JSON
                    raise EntityProcessingError(
                        f"JSON contains binary data ({replacement_count} replacement chars)"
                    )

            data = json.loads(text)
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

        Raises:
            EntityProcessingError: If XML contains corrupted data
        """

        def _read_and_format():
            # Read raw bytes
            with open(path, "rb") as f:
                raw_bytes = f.read()

            # Try UTF-8 first
            try:
                content = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                # Fallback with replace to detect corruption
                content = raw_bytes.decode("utf-8", errors="replace")
                replacement_count = content.count("\ufffd")
                if replacement_count > 50:  # Strict for XML
                    raise EntityProcessingError(
                        f"XML contains binary data ({replacement_count} replacement chars)"
                    )

            dom = xml.dom.minidom.parseString(content)
            formatted = dom.toprettyxml()
            return f"```xml\n{formatted}\n```"

        try:
            return await run_in_thread_pool(_read_and_format)
        except EntityProcessingError:
            raise
        except Exception as e:
            logger.warning(f"XML parsing failed for {path}: {e}, using raw content")
            # Fallback to raw content - read with validation
            with open(path, "rb") as f:
                raw_bytes = f.read()

            try:
                raw = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                raw = raw_bytes.decode("utf-8", errors="replace")
                replacement_count = raw.count("\ufffd")
                if replacement_count > 100:  # More lenient for fallback
                    raise EntityProcessingError(
                        f"XML contains excessive binary data ({replacement_count} replacement chars)"
                    )

            return f"```xml\n{raw}\n```" if raw.strip() else None
