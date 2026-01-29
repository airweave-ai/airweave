"""Query embedding schemas for spotlight search."""

from typing import Optional

from pydantic import BaseModel, Field


class SpotlightSparseEmbedding(BaseModel):
    """Sparse embedding schema."""

    indices: list[int] = Field(..., description="Token indices with non-zero values.")
    values: list[float] = Field(..., description="Weights for each token index.")


class SpotlightDenseEmbedding(BaseModel):
    """Dense embedding schema."""

    vector: list[float] = Field(..., description="The dense embedding of the query.")


class SpotlightQueryEmbeddings(BaseModel):
    """Query embeddings schema."""

    dense_embeddings: Optional[list[SpotlightDenseEmbedding]] = Field(
        default=None, description="Dense embeddings for all query variations."
    )
    sparse_embedding: Optional[SpotlightSparseEmbedding] = Field(
        default=None, description="Sparse embedding for the primary query only."
    )
