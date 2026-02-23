"""Query embedding schemas for agentic search.

These are thin aliases importing from the embedder domain schemas.
"""

from typing import Optional

from pydantic import BaseModel, Field

from airweave.domains.embedders.schemas import DenseEmbedding as AgenticSearchDenseEmbedding
from airweave.domains.embedders.schemas import SparseEmbedding as AgenticSearchSparseEmbedding

# Re-export for backward compatibility
__all__ = [
    "AgenticSearchDenseEmbedding",
    "AgenticSearchSparseEmbedding",
    "AgenticSearchQueryEmbeddings",
]


class AgenticSearchQueryEmbeddings(BaseModel):
    """Query embeddings schema."""

    dense_embeddings: Optional[list[AgenticSearchDenseEmbedding]] = Field(
        default=None, description="Dense embeddings for all query variations."
    )
    sparse_embedding: Optional[AgenticSearchSparseEmbedding] = Field(
        default=None, description="Sparse embedding for the primary query only."
    )
