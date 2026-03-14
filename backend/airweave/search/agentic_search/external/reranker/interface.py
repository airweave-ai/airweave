"""Reranker protocol for agentic search."""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class RerankerResult:
    """A single reranked result with its index and relevance score."""

    index: int
    relevance_score: float


class AgenticSearchRerankerInterface(Protocol):
    """Protocol for reranking search results."""

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int | None = None,
    ) -> list[RerankerResult]:
        """Rerank documents by relevance to a query.

        Args:
            query: The search query.
            documents: List of document texts to rerank.
            top_n: Maximum number of results to return. None means all.

        Returns:
            List of RerankerResult ordered by relevance (highest first).
        """
        ...
