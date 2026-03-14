"""Cohere reranker implementation."""

from __future__ import annotations

import cohere

from airweave.adapters.reranker.exceptions import RerankerError
from airweave.adapters.reranker.types import RerankerResult

COHERE_RERANK_MODEL = "rerank-v4.0-pro"
COHERE_MAX_DOCUMENTS = 1000

# Our chunker (SemanticChunker) guarantees textual_representation is at most
# 8192 tokens (tiktoken cl100k_base). Setting max_tokens_per_doc to match means
# Cohere accepts every document without truncation.
COHERE_MAX_TOKENS_PER_DOC = 8192


class CohereReranker:
    """Reranker using Cohere's rerank API."""

    def __init__(self, api_key: str) -> None:
        """Initialize with Cohere API key."""
        self._client = cohere.AsyncClientV2(api_key=api_key)

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int | None = None,
    ) -> list[RerankerResult]:
        """Rerank documents using Cohere rerank API.

        Raises:
            RerankerError: If the Cohere API call fails or document limit exceeded.
        """
        if len(documents) > COHERE_MAX_DOCUMENTS:
            raise RerankerError(
                f"Cohere rerank: {len(documents)} documents "
                f"exceeds the API limit of {COHERE_MAX_DOCUMENTS}"
            )

        try:
            response = await self._client.rerank(
                model=COHERE_RERANK_MODEL,
                query=query,
                documents=documents,
                top_n=top_n if top_n is not None else len(documents),
                max_tokens_per_doc=COHERE_MAX_TOKENS_PER_DOC,
            )
        except Exception as e:
            raise RerankerError(f"Cohere rerank failed: {e}", cause=e) from e

        return [
            RerankerResult(index=r.index, relevance_score=r.relevance_score)
            for r in response.results
        ]
