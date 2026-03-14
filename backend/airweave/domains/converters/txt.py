"""Text file to markdown converter."""

import asyncio
import json
import os
import xml.dom.minidom
from typing import Dict, List

import aiofiles

from airweave.core.logging import logger
from airweave.domains.converters._base import BaseTextConverter
from airweave.domains.sync_pipeline.async_helpers import run_in_thread_pool
from airweave.domains.sync_pipeline.exceptions import EntityProcessingError


class TxtConverter(BaseTextConverter):
    """Converts text files (TXT, JSON, XML, MD, YAML, TOML) to markdown."""

    async def convert_batch(self, file_paths: List[str]) -> Dict[str, str]:
        """Convert text files to markdown."""
        logger.debug(f"Converting {len(file_paths)} text files to markdown...")

        results = {}
        semaphore = asyncio.Semaphore(20)

        async def _convert_one(path: str):
            async with semaphore:
                try:
                    _, ext = os.path.splitext(path)
                    ext = ext.lower()

                    if ext == ".json":
                        text = await self._convert_json(path)
                    elif ext == ".xml":
                        text = await self._convert_xml(path)
                    else:
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

    @staticmethod
    def _try_chardet_decode(raw_bytes: bytes, path: str) -> str | None:
        try:
            import chardet

            detection = chardet.detect(raw_bytes[:100000])
            if not detection or detection.get("confidence", 0) <= 0.7:
                return None
            detected_encoding = detection["encoding"]
            if not detected_encoding:
                return None
            text = raw_bytes.decode(detected_encoding)
            if text.count("\ufffd") == 0:
                logger.debug(f"Detected encoding {detected_encoding} for {os.path.basename(path)}")
                return text
        except (UnicodeDecodeError, LookupError):
            pass
        except ImportError:
            logger.debug("chardet not available, falling back to UTF-8 with ignore")
        return None

    async def _convert_plain_text(self, path: str) -> str:
        async with aiofiles.open(path, "rb") as f:
            raw_bytes = await f.read()

        if not raw_bytes:
            return ""

        try:
            text = raw_bytes.decode("utf-8")
            if text.count("\ufffd") == 0:
                return text
        except UnicodeDecodeError:
            pass

        chardet_result = self._try_chardet_decode(raw_bytes, path)
        if chardet_result is not None:
            return chardet_result

        text = raw_bytes.decode("utf-8", errors="replace")
        replacement_count = text.count("\ufffd")

        if replacement_count > 0:
            text_length = len(text)
            replacement_ratio = replacement_count / text_length if text_length > 0 else 0

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
        def _read_and_format():
            with open(path, "rb") as f:
                raw_bytes = f.read()

            try:
                text = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text = raw_bytes.decode("utf-8", errors="replace")
                replacement_count = text.count("\ufffd")
                if replacement_count > 50:
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
        def _read_and_format():
            with open(path, "rb") as f:
                raw_bytes = f.read()

            try:
                content = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                content = raw_bytes.decode("utf-8", errors="replace")
                replacement_count = content.count("\ufffd")
                if replacement_count > 50:
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
            with open(path, "rb") as f:
                raw_bytes = f.read()

            try:
                raw = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                raw = raw_bytes.decode("utf-8", errors="replace")
                replacement_count = raw.count("\ufffd")
                if replacement_count > 100:
                    raise EntityProcessingError(
                        f"XML contains excessive binary data "
                        f"({replacement_count} replacement chars)"
                    )

            return f"```xml\n{raw}\n```" if raw.strip() else None
