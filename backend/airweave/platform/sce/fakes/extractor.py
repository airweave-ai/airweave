"""Fake extractor for testing.

Records all calls for assertion. Returns canned refs configured at init.
"""

from typing import List, Optional

from airweave.platform.sce.types import ExtractedRef


class FakeExtractor:
    """In-memory fake for ExtractorProtocol."""

    def __init__(
        self,
        refs: Optional[List[ExtractedRef]] = None,
        *,
        should_raise: Optional[Exception] = None,
    ) -> None:
        """Initialize with optional canned refs and error injection."""
        self._refs = refs or []
        self._calls: list[tuple[str, ...]] = []
        self._should_raise = should_raise

    async def extract(self, text: str) -> List[ExtractedRef]:
        """Record call and return canned refs."""
        self._calls.append(("extract", text))
        if self._should_raise:
            raise self._should_raise
        return list(self._refs)

    # --- Assertion helpers ---

    def assert_called(self, method_name: str) -> tuple:
        """Assert a method was called and return the call tuple."""
        for call in self._calls:
            if call[0] == method_name:
                return call
        raise AssertionError(f"{method_name} was not called")

    def assert_not_called(self, method_name: str) -> None:
        """Assert a method was never called."""
        for call in self._calls:
            if call[0] == method_name:
                raise AssertionError(f"{method_name} was called unexpectedly")

    def call_count(self, method_name: str) -> int:
        """Return number of times a method was called."""
        return sum(1 for name, *_ in self._calls if name == method_name)

    def get_calls(self, method_name: str) -> list[tuple]:
        """Return all calls for a method."""
        return [call for call in self._calls if call[0] == method_name]
