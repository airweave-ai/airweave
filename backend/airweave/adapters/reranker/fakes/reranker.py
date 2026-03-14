"""In-memory fake for RerankerProtocol."""

from airweave.adapters.reranker.types import RerankerResult


class FakeReranker:
    """In-memory fake for RerankerProtocol.

    Returns pre-seeded reranking results.
    """

    def __init__(self) -> None:
        self._results: list[RerankerResult] = []
        self._calls: list[tuple] = []

    def seed_results(self, results: list[RerankerResult]) -> None:
        """Seed results to be returned by rerank."""
        self._results = results

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int | None = None,
    ) -> list[RerankerResult]:
        """Return seeded results."""
        self._calls.append(("rerank", query, documents, top_n))
        if self._results:
            return self._results

        # Default: return identity ordering with linear scores
        limit = top_n if top_n is not None else len(documents)
        return [
            RerankerResult(index=i, relevance_score=1.0 - (i * 0.1))
            for i in range(min(limit, len(documents)))
        ]
