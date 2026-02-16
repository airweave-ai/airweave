"""Query embedding schemas for agentic search."""

from typing import Optional

from pydantic import BaseModel, Field


class AgenticSearchSparseEmbedding(BaseModel):
    """Sparse embedding schema."""

    indices: list[int] = Field(..., description="Token indices with non-zero values.")
    values: list[float] = Field(..., description="Weights for each token index.")


class AgenticSearchDenseEmbedding(BaseModel):
    """Dense embedding schema."""

    vector: list[float] = Field(..., description="The dense embedding of the query.")


class AgenticSearchQueryEmbeddings(BaseModel):
    """Query embeddings schema."""

    dense_embeddings: Optional[list[AgenticSearchDenseEmbedding]] = Field(
        default=None, description="Dense embeddings for all query variations."
    )
    sparse_embedding: Optional[AgenticSearchSparseEmbedding] = Field(
        default=None, description="Sparse embedding for the primary query only."
    )
