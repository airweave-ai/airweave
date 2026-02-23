"""Typed embedding output schemas.

All embedder methods return these types. Callers never deal with
raw ``list[list[float]]`` or fastembed's internal ``SparseEmbedding``.
"""

from pydantic import BaseModel, Field


class DenseEmbedding(BaseModel):
    """Single dense embedding vector."""

    vector: list[float] = Field(..., description="The dense embedding vector.")


class SparseEmbedding(BaseModel):
    """Single sparse embedding (BM25 token weights)."""

    indices: list[int] = Field(..., description="Token indices with non-zero values.")
    values: list[float] = Field(..., description="Weights for each token index.")
