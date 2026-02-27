"""Types for the embedders domain."""

from pydantic import BaseModel, Field

from airweave.core.protocols.registry import BaseRegistryEntry

# ---------------------------------------------------------------------------
# Embedding value types
# ---------------------------------------------------------------------------


class DenseEmbedding(BaseModel):
    """A dense embedding vector."""

    vector: list[float] = Field(..., description="The dense embedding vector.")


class SparseEmbedding(BaseModel):
    """A sparse embedding with token indices and weights."""

    indices: list[int] = Field(..., description="Token indices with non-zero values.")
    values: list[float] = Field(..., description="Weights for each token index.")


# ---------------------------------------------------------------------------
# Registry entry types
# ---------------------------------------------------------------------------


class DenseEmbedderEntry(BaseRegistryEntry):
    """A registered dense embedding model.

    Each entry represents one (provider, model) pair — e.g.
    ("openai", "text-embedding-3-small") is a separate entry from
    ("openai", "text-embedding-3-large").
    """

    provider: str
    api_model_name: str
    max_dimensions: int
    max_tokens: int
    supports_matryoshka: bool
    embedder_class_ref: type
    required_setting: str | None = None


class SparseEmbedderEntry(BaseRegistryEntry):
    """A registered sparse embedding model."""

    provider: str
    api_model_name: str
    embedder_class_ref: type
    required_setting: str | None = None
