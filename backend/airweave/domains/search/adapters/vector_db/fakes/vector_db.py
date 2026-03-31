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
    Supports per-method error injection via seed_*_error() methods.
    """

    def __init__(self) -> None:
        self._results: SearchResults = SearchResults()
        self._count: int = 0
        self._filter_results: list[SearchResult] = []
        self._calls: list[tuple] = []

        self._compile_error: Exception | None = None
        self._execute_error: Exception | None = None
        self._count_error: Exception | None = None
        self._filter_error: Exception | None = None

    def seed_results(self, results: SearchResults) -> None:
        """Seed results to be returned by execute_query."""
        self._results = results

    def seed_count(self, count: int) -> None:
        """Seed count to be returned by count."""
        self._count = count

    def seed_filter_results(self, results: list[SearchResult]) -> None:
        """Seed results to be returned by filter_search."""
        self._filter_results = results

    def seed_compile_error(self, error: Exception) -> None:
        """Inject an error to raise on next compile_query call (single-shot)."""
        self._compile_error = error

    def seed_execute_error(self, error: Exception) -> None:
        """Inject an error to raise on next execute_query call (single-shot)."""
        self._execute_error = error

    def seed_count_error(self, error: Exception) -> None:
        """Inject an error to raise on next count call (single-shot)."""
        self._count_error = error

    def seed_filter_error(self, error: Exception) -> None:
        """Inject an error to raise on next filter_search call (single-shot)."""
        self._filter_error = error

    async def compile_query(
        self,
        plan: SearchPlan,
        embeddings: QueryEmbeddings,
        collection_id: str,
        acl_principals: list[str] | None = None,
    ) -> CompiledQuery:
        """Return a fake compiled query, or raise seeded error."""
        self._calls.append(("compile_query", plan, embeddings, collection_id))
        if self._compile_error:
            err = self._compile_error
            self._compile_error = None
            raise err
        return CompiledQuery(
            vector_db="fake",
            display="fake query",
            raw={"plan": plan.model_dump(), "collection_id": collection_id},
        )

    async def execute_query(
        self,
        compiled_query: CompiledQuery,
    ) -> SearchResults:
        """Return seeded results, or raise seeded error."""
        self._calls.append(("execute_query", compiled_query))
        if self._execute_error:
            err = self._execute_error
            self._execute_error = None
            raise err
        return self._results

    async def count(
        self,
        filter_groups: list[FilterGroup],
        collection_id: str,
    ) -> int:
        """Return seeded count, or raise seeded error."""
        self._calls.append(("count", filter_groups, collection_id))
        if self._count_error:
            err = self._count_error
            self._count_error = None
            raise err
        return self._count

    async def filter_search(
        self,
        filter_groups: list[FilterGroup],
        collection_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SearchResult]:
        """Return seeded filter results, or raise seeded error."""
        self._calls.append(("filter_search", filter_groups, collection_id, limit, offset))
        if self._filter_error:
            err = self._filter_error
            self._filter_error = None
            raise err
        return self._filter_results

    async def close(self) -> None:
        """No-op cleanup."""
        self._calls.append(("close",))
