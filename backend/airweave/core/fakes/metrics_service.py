"""Fake metrics service for testing."""

from airweave.core.protocols.metrics import (
    AgenticSearchMetrics,
    DbPool,
    DbPoolMetrics,
    HttpMetrics,
    MetricsService,
)


class FakeMetricsService(MetricsService):
    """In-memory MetricsService stand-in for testing.

    Structurally satisfies the ``MetricsService`` protocol — matching
    every other fake in the codebase.
    """

    def __init__(
        self,
        http: HttpMetrics,
        agentic_search: AgenticSearchMetrics,
        db_pool: DbPoolMetrics,
    ) -> None:
        self.http = http
        self.agentic_search = agentic_search
        self.db_pool = db_pool

    async def start(self, *, pool: DbPool) -> None:
        pass

    async def stop(self) -> None:
        pass
