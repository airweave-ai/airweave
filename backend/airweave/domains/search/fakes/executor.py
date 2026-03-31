"""In-memory fake for SearchPlanExecutorProtocol."""

from __future__ import annotations

from typing import Any

from airweave.domains.search.protocols import SearchPlanExecutorProtocol
from airweave.domains.search.types import FilterGroup, SearchPlan, SearchResults


class FakeSearchPlanExecutor(SearchPlanExecutorProtocol):
    """Returns seeded or empty SearchResults. Records calls.

    Supports error injection and multi-call sequences.
    """

    def __init__(self) -> None:
        self._result: SearchResults = SearchResults(results=[])
        self._sequence: list[SearchResults | Exception] = []
        self._calls: list[tuple] = []
        self._error: Exception | None = None

    def seed_result(self, result: SearchResults) -> None:
        """Seed the result to return on next execute call."""
        self._result = result

    def seed_error(self, error: Exception) -> None:
        """Inject an error to raise on next execute call (single-shot)."""
        self._error = error

    def seed_result_sequence(self, sequence: list[SearchResults | Exception]) -> None:
        """Seed a sequence of results/errors for successive execute calls."""
        self._sequence = list(sequence)

    async def execute(
        self,
        plan: SearchPlan,
        user_filter: list[FilterGroup],
        collection_id: str,
        db: Any = None,
        ctx: Any = None,
        collection_readable_id: str = "",
        user_principal: str | None = None,
    ) -> SearchResults:
        """Record the call and return seeded result, or raise seeded error."""
        self._calls.append(("execute", plan, user_filter, collection_id))
        if self._error:
            err = self._error
            self._error = None
            raise err
        if self._sequence:
            item = self._sequence.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        return self._result
