"""Query embedding schemas for agentic search."""

from typing import Optional

from pydantic import BaseModel, Field

from airweave.domains.embedders.types import DenseEmbedding, SparseEmbedding


class AgenticSearchQueryEmbeddings(BaseModel):
    """Query embeddings schema."""

    dense_embeddings: Optional[list[DenseEmbedding]] = Field(
        default=None, description="Dense embeddings for all query variations."
    )
    sparse_embedding: Optional[SparseEmbedding] = Field(
        default=None, description="Sparse embedding for the primary query only."
    )
