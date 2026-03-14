"""Reranker provider protocol.

Defines the structural typing contract that any reranker backend must satisfy.
Uses :class:`typing.Protocol` so implementations don't need to inherit.

Usage::

    from airweave.core.protocols.reranker import RerankerProtocol, RerankerResult


    async def search(reranker: RerankerProtocol) -> list[RerankerResult]:
        return await reranker.rerank(query, documents, top_n=10)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class RerankerResult:
    """A single reranked result with its index and relevance score."""

    index: int
    relevance_score: float


@runtime_checkable
class RerankerProtocol(Protocol):
    """Structural protocol for reranker providers.

    Any class that implements an async ``rerank`` method with this
    exact signature is considered a valid reranker provider -- no subclassing
    required.
    """

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
