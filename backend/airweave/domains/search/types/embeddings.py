"""Embedding types for the search module.

QueryEmbeddings.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from airweave.domains.embedders.types import DenseEmbedding, SparseEmbedding


class QueryEmbeddings(BaseModel):
    """Query embeddings schema."""

    dense_embeddings: Optional[list[DenseEmbedding]] = Field(
        default=None, description="Dense embeddings for all query variations."
    )
    sparse_embedding: Optional[SparseEmbedding] = Field(
        default=None, description="Sparse embedding for the primary query only."
    )
