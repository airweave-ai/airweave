"""OpenAI Embedding Client for agentic search.

Lightweight embedder for query embedding in the agentic search loop.
Generates both dense (3072-dim) and sparse (BM25) embeddings for Vespa search.

This is separate from platform/embedders because:
- It's optimized for few queries (1-5), not thousands of entities
- No complex batching, rate limiting, or concurrent request handling needed
- Simpler error handling (fail-fast, no zero-vector fallback)
"""

from dataclasses import dataclass
from typing import List, Optional

from fastembed import SparseEmbedding

from airweave.api.context import ApiContext
from airweave.core.config import settings
from airweave.platform.embedders import SparseEmbedder
from airweave.search.agentic_search.planner.schemas import RetrievalStrategy
from openai import AsyncOpenAI


@dataclass
class QueryEmbeddings:
    """Container for query embeddings.

    Holds both dense (semantic) and sparse (keyword) embeddings for search queries.
    Used by the YQL builder to construct Vespa query parameters.

    Note:
        - Dense embeddings are generated for ALL queries (multi-query nearestNeighbor)
        - Sparse embedding is generated for the FIRST query only (keyword/BM25 scoring)
        - This matches how Vespa uses them: all queries for ANN, primary query for BM25
    """

    queries: List[str]
    dense: Optional[List[List[float]]] = None  # 3072-dim embeddings for ALL queries
    sparse: Optional[SparseEmbedding] = None  # FastEmbed BM25 for FIRST query only


class AgenticEmbedder:
    """Lightweight embedder for agentic search queries.

    Generates embeddings for 1-5 search queries per iteration.
    Unlike the sync pipeline's DenseEmbedder, this doesn't need:
    - Complex batching (we only embed a few queries)
    - Rate limiting (single request per iteration)
    - Concurrent request handling
    - Graceful degradation (fail-fast is fine for search)

    Usage:
        embedder = AgenticEmbedder(ctx=ctx)
        embeddings = await embedder.embed(
            queries=["search query 1", "query 2"],
            strategy=RetrievalStrategy.HYBRID,
        )
    """

    # OpenAI text-embedding-3-large configuration
    MODEL = "text-embedding-3-large"
    DIMENSIONS = 3072

    def __init__(self, ctx: Optional[ApiContext] = None) -> None:
        """Initialize the embedder.

        Args:
            ctx: API context for logging (optional)
        """
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")

        self._client = AsyncOpenAI(api_key=api_key, timeout=60.0, max_retries=2)
        self._sparse_embedder = SparseEmbedder()
        self._ctx = ctx

    def _log(self, message: str, level: str = "debug") -> None:
        """Log a message if context is available."""
        if self._ctx:
            logger = getattr(self._ctx.logger, level)
            logger(f"[AgenticEmbedder] {message}")

    async def embed(
        self,
        queries: List[str],
        strategy: RetrievalStrategy,
    ) -> QueryEmbeddings:
        """Generate embeddings for search queries based on retrieval strategy.

        Args:
            queries: List of 1-5 search queries to embed
            strategy: Retrieval strategy determines which embeddings to generate:
                - SEMANTIC: dense only (all queries)
                - KEYWORD: sparse only (first query)
                - HYBRID: dense (all queries) + sparse (first query)

        Returns:
            QueryEmbeddings with dense and/or sparse embeddings

        Raises:
            ValueError: If queries is empty or contains empty strings
            RuntimeError: If embedding API call fails
        """
        if not queries:
            raise ValueError("No queries to embed")

        for i, q in enumerate(queries):
            if not q or not q.strip():
                raise ValueError(f"Empty query at index {i}")

        self._log(f"Embedding {len(queries)} queries with strategy={strategy.value}")

        dense = None
        sparse = None

        # Generate dense embeddings for ALL queries (multi-query nearestNeighbor)
        if strategy in (RetrievalStrategy.SEMANTIC, RetrievalStrategy.HYBRID):
            dense = await self._embed_dense(queries)
            self._log(f"Dense embeddings: {len(dense)} x {self.DIMENSIONS}-dim")

        # Generate sparse embedding for FIRST query only (BM25 keyword scoring)
        if strategy in (RetrievalStrategy.KEYWORD, RetrievalStrategy.HYBRID):
            sparse = await self._embed_sparse(queries[0])
            self._log("Sparse embedding: 1 vector (primary query)")

        return QueryEmbeddings(queries=queries, dense=dense, sparse=sparse)

    async def _embed_dense(self, queries: List[str]) -> List[List[float]]:
        """Generate dense 3072-dim embeddings via OpenAI.

        Args:
            queries: List of query strings

        Returns:
            List of 3072-dim embedding vectors

        Raises:
            RuntimeError: On API failure
        """
        try:
            response = await self._client.embeddings.create(
                input=queries,
                model=self.MODEL,
                dimensions=self.DIMENSIONS,
                encoding_format="float",
            )

            embeddings = [e.embedding for e in response.data]

            # Validate
            if len(embeddings) != len(queries):
                raise RuntimeError(f"Got {len(embeddings)} embeddings for {len(queries)} queries")
            if embeddings and len(embeddings[0]) != self.DIMENSIONS:
                raise RuntimeError(
                    f"Got {len(embeddings[0])}-dim vectors, expected {self.DIMENSIONS}"
                )

            return embeddings

        except Exception as e:
            self._log(f"Dense embedding failed: {e}", level="error")
            raise RuntimeError(f"Dense embedding failed: {e}") from e

    async def _embed_sparse(self, query: str) -> SparseEmbedding:
        """Generate sparse BM25 embedding for the primary query.

        Only the first/primary query needs sparse embedding because Vespa
        uses it for BM25 keyword scoring. Additional queries are matched
        semantically only via nearestNeighbor.

        Args:
            query: The primary query string

        Returns:
            SparseEmbedding object

        Raises:
            RuntimeError: On embedding failure
        """
        try:
            return await self._sparse_embedder.embed(query)

        except Exception as e:
            self._log(f"Sparse embedding failed: {e}", level="error")
            raise RuntimeError(f"Sparse embedding failed: {e}") from e
