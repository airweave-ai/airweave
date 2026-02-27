"""Query embedding operation.

Converts text queries into vector embeddings for similarity search.
Generates dense neural embeddings and/or sparse BM25 embeddings based on
the retrieval strategy (hybrid, neural, or keyword).
"""

from typing import TYPE_CHECKING, List, Optional

from airweave.api.context import ApiContext
from airweave.domains.embedders.protocols import DenseEmbedderProtocol, SparseEmbedderProtocol
from airweave.schemas.search import RetrievalStrategy
from airweave.search.context import SearchContext

from ._base import SearchOperation

if TYPE_CHECKING:
    from airweave.search.state import SearchState


class EmbedQuery(SearchOperation):
    """Generate vector embeddings for queries."""

    def __init__(
        self,
        strategy: RetrievalStrategy,
        dense_embedder: DenseEmbedderProtocol,
        sparse_embedder: SparseEmbedderProtocol,
    ) -> None:
        """Initialize with retrieval strategy and domain embedders."""
        self.strategy = strategy
        self.dense_embedder = dense_embedder
        self.sparse_embedder = sparse_embedder

    def depends_on(self) -> List[str]:
        """Depends on query expansion to get all queries to embed."""
        return ["QueryExpansion"]

    async def execute(
        self,
        context: SearchContext,
        state: "SearchState",
        ctx: ApiContext,
    ) -> None:
        """Generate embeddings for queries."""
        ctx.logger.debug("[EmbedQuery] Generating embeddings for queries")

        # Emit embedding start
        await context.emitter.emit(
            "embedding_start",
            {"search_method": self.strategy.value},
            op_name=self.__class__.__name__,
        )

        # Determine queries to embed (expanded + original, or just original)
        queries = self._get_queries_to_embed(context, state)

        # Generate dense embeddings if needed
        if self.strategy in (RetrievalStrategy.HYBRID, RetrievalStrategy.NEURAL):
            dense_embeddings = await self._generate_dense_embeddings(queries, ctx)
        else:
            # Keyword-only doesn't need dense embeddings
            dense_embeddings = None

        # Generate sparse BM25 embeddings if needed
        if self.strategy in (RetrievalStrategy.HYBRID, RetrievalStrategy.KEYWORD):
            sparse_embeddings = await self._generate_sparse_embeddings(queries, ctx)
        else:
            sparse_embeddings = None

        # Write to state - embeddings are REQUIRED, never write None
        if dense_embeddings is None and sparse_embeddings is None:
            raise RuntimeError(
                f"No embeddings generated for strategy {self.strategy}. This is a bug."
            )

        state.dense_embeddings = dense_embeddings
        state.sparse_embeddings = sparse_embeddings

        # Report metrics for analytics
        self._report_metrics(
            state,
            embeddings_generated=len(dense_embeddings or sparse_embeddings or []),
            has_dense=dense_embeddings is not None,
            has_sparse=sparse_embeddings is not None,
            strategy=self.strategy.value,
        )

        # Emit embedding done with stats
        await self._emit_embedding_done(dense_embeddings, sparse_embeddings, context.emitter)

    def _get_queries_to_embed(self, context: SearchContext, state: "SearchState") -> List[str]:
        """Get all queries to embed (original + expanded)."""
        queries = [context.query]

        # Add expanded queries if available
        if state.expanded_queries:
            queries.extend(state.expanded_queries)

        if not queries:
            raise ValueError("No queries to embed")

        return queries

    async def _generate_dense_embeddings(
        self, queries: List[str], ctx: ApiContext
    ) -> List[List[float]]:
        """Generate dense neural embeddings using the domain embedder."""
        ctx.logger.debug(
            f"[EmbedQuery] Generating {self.dense_embedder.dimensions}-dim embeddings "
            f"for {len(queries)} queries"
        )
        results = await self.dense_embedder.embed_many(queries)

        # Validate we got embeddings for all queries
        if len(results) != len(queries):
            raise RuntimeError(
                f"Embedding count mismatch: got {len(results)} for {len(queries)} queries"
            )

        # Extract raw vectors to match SearchState type (List[List[float]])
        dense_embeddings = [emb.vector for emb in results]

        ctx.logger.debug(
            f"[EmbedQuery] Dense embeddings generated: {len(dense_embeddings)} x "
            f"{len(dense_embeddings[0]) if dense_embeddings else 0}-dim"
        )

        return dense_embeddings

    async def _generate_sparse_embeddings(self, queries: List[str], ctx: ApiContext) -> List:
        """Generate sparse BM25 embeddings for keyword search."""
        if len(queries) == 1:
            sparse_embedding = await self.sparse_embedder.embed(queries[0])
            sparse_embeddings = [sparse_embedding]
        else:
            sparse_embeddings = await self.sparse_embedder.embed_many(queries)

        # Validate we got embeddings for all queries
        if len(sparse_embeddings) != len(queries):
            raise RuntimeError(
                f"Sparse embedding count mismatch: got {len(sparse_embeddings)} "
                f"for {len(queries)} queries"
            )

        ctx.logger.debug(f"[EmbedQuery] Sparse embeddings generated: {len(sparse_embeddings)}")

        return sparse_embeddings

    async def _emit_embedding_done(
        self,
        dense_embeddings: Optional[List[List[float]]],
        sparse_embeddings: Optional[List],
        emitter,
    ) -> None:
        """Emit embedding_done event with statistics.

        Args:
            dense_embeddings: Dense neural embeddings (or None)
            sparse_embeddings: Sparse BM25 embeddings (or None)
            emitter: Event emitter for streaming
        """
        neural_count = len(dense_embeddings) if dense_embeddings else 0
        sparse_count = len(sparse_embeddings) if sparse_embeddings else 0
        dim = len(dense_embeddings[0]) if dense_embeddings and dense_embeddings else None

        # Calculate average non-zeros for sparse embeddings
        avg_nonzeros = None
        if sparse_embeddings:
            try:
                nonzeros = [
                    len(getattr(v, "indices", []))
                    for v in sparse_embeddings
                    if hasattr(v, "indices")
                ]
                if nonzeros:
                    avg_nonzeros = sum(nonzeros) / len(nonzeros)
            except Exception:
                pass

        await emitter.emit(
            "embedding_done",
            {
                "neural_count": neural_count,
                "sparse_count": sparse_count,
                "dim": dim,
                "model": self.dense_embedder.model_name if dense_embeddings else None,
                "avg_nonzeros": avg_nonzeros,
            },
            op_name=self.__class__.__name__,
        )
