"""In-memory fake for SearchPlanExecutorProtocol."""

from __future__ import annotations

from typing import Any

from airweave.domains.search.protocols import SearchPlanExecutorProtocol
from airweave.domains.search.types import FilterGroup, SearchPlan, SearchResults


class FakeSearchPlanExecutor(SearchPlanExecutorProtocol):
    """Returns seeded or empty SearchResults. Records calls."""

    def __init__(self) -> None:
        self._result: SearchResults = SearchResults(results=[])
        self._calls: list[tuple] = []

    def seed_result(self, result: SearchResults) -> None:
        """Seed the result to return on next execute call."""
        self._result = result

    async def execute(
        self,
        plan: SearchPlan,
        user_filter: list[FilterGroup],
        collection_id: str,
        db: Any = None,
        ctx: Any = None,
        collection_readable_id: str = "",
    ) -> SearchResults:
        """Record the call and return seeded result."""
        self._calls.append(("execute", plan, user_filter, collection_id))
        return self._result
