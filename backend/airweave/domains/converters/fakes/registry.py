"""Fake converter registry for testing."""

from __future__ import annotations

from typing import Dict, List, Optional

from airweave.domains.converters._base import BaseTextConverter


class _StubConverter(BaseTextConverter):
    """Returns canned markdown for every file/URL."""

    def __init__(self, text: str = "fake-markdown") -> None:
        self._text = text

    async def convert_batch(self, file_paths: List[str]) -> Dict[str, str]:
        return {p: self._text for p in file_paths}


class FakeConverterRegistry:
    """In-memory registry returning stub converters for all lookups."""

    def __init__(self, text: str = "fake-markdown") -> None:
        self._stub = _StubConverter(text)

    def for_extension(self, ext: str) -> Optional[BaseTextConverter]:
        return self._stub

    def for_web(self) -> BaseTextConverter:
        return self._stub
