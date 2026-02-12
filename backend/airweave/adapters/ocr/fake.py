"""Fake OCR provider for testing.

Returns canned markdown without calling any external API.
"""

from __future__ import annotations

from typing import Dict, List, Optional


class FakeOcrProvider:
    """Test implementation of OcrProvider.

    Returns configurable markdown for each file path. Records all calls
    for assertions.

    Usage::

        fake = FakeOcrProvider(default_markdown="# Hello")
        results = await fake.convert_batch(["/tmp/doc.pdf"])
        assert results["/tmp/doc.pdf"] == "# Hello"
    """

    def __init__(
        self,
        default_markdown: Optional[str] = "# Fake OCR output",
        overrides: Optional[Dict[str, Optional[str]]] = None,
    ) -> None:
        """Initialize the fake.

        Args:
            default_markdown: Markdown returned for any file without an
                explicit override. Set to ``None`` to simulate failure.
            overrides: Per-path overrides (path → markdown or ``None``).
        """
        self._default = default_markdown
        self._overrides: Dict[str, Optional[str]] = overrides or {}
        self.calls: list[List[str]] = []

    async def convert_batch(self, file_paths: List[str]) -> Dict[str, Optional[str]]:
        """Return canned results and record the call."""
        self.calls.append(list(file_paths))
        return {path: self._overrides.get(path, self._default) for path in file_paths}

    # Test helpers

    @property
    def call_count(self) -> int:
        """Number of times convert_batch was called."""
        return len(self.calls)

    @property
    def all_paths(self) -> list[str]:
        """Flat list of every file path across all calls."""
        return [p for call in self.calls for p in call]

    def clear(self) -> None:
        """Reset recorded calls."""
        self.calls.clear()
