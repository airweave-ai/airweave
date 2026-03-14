"""In-memory fake for VectorDBProtocol."""

from airweave.domains.search.types.embeddings import QueryEmbeddings
from airweave.domains.search.types.filters import FilterGroup
from airweave.domains.search.types.plan import SearchPlan
from airweave.domains.search.types.results import (
    CompiledQuery,
    SearchResult,
    SearchResults,
)


class FakeVectorDB:
    """In-memory fake for VectorDBProtocol.

    Seed results before use. Calls are recorded for verification.
    """

    def __init__(self) -> None:
        self._results: SearchResults = SearchResults()
        self._count: int = 0
        self._filter_results: list[SearchResult] = []
        self._calls: list[tuple] = []

    def seed_results(self, results: SearchResults) -> None:
        """Seed results to be returned by execute_query."""
        self._results = results

    def seed_count(self, count: int) -> None:
        """Seed count to be returned by count."""
        self._count = count

    def seed_filter_results(self, results: list[SearchResult]) -> None:
        """Seed results to be returned by filter_search."""
        self._filter_results = results

    async def compile_query(
        self,
        plan: SearchPlan,
        embeddings: QueryEmbeddings,
        collection_id: str,
    ) -> CompiledQuery:
        """Return a fake compiled query."""
        self._calls.append(("compile_query", plan, embeddings, collection_id))
        return CompiledQuery(
            vector_db="fake",
            display="fake query",
            raw={"plan": plan.model_dump(), "collection_id": collection_id},
        )

    async def execute_query(
        self,
        compiled_query: CompiledQuery,
    ) -> SearchResults:
        """Return seeded results."""
        self._calls.append(("execute_query", compiled_query))
        return self._results

    async def count(
        self,
        filter_groups: list[FilterGroup],
        collection_id: str,
    ) -> int:
        """Return seeded count."""
        self._calls.append(("count", filter_groups, collection_id))
        return self._count

    async def filter_search(
        self,
        filter_groups: list[FilterGroup],
        collection_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SearchResult]:
        """Return seeded filter results."""
        self._calls.append(("filter_search", filter_groups, collection_id, limit, offset))
        return self._filter_results

    async def close(self) -> None:
        """No-op cleanup."""
        self._calls.append(("close",))
