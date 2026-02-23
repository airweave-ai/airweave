"""Sparse embedder model registry."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SparseModelSpec:
    """Specification for a sparse embedding model."""

    model_name: str


SPARSE_MODEL_REGISTRY: dict[str, SparseModelSpec] = {
    "fastembed": SparseModelSpec(model_name="Qdrant/bm25"),
}


def get_model_spec(provider: str = "fastembed") -> SparseModelSpec:
    """Get the model spec for a sparse embedder provider.

    Args:
        provider: Provider name (default: "fastembed").

    Returns:
        SparseModelSpec for the provider.

    Raises:
        ValueError: If provider is unknown.
    """
    spec = SPARSE_MODEL_REGISTRY.get(provider)
    if not spec:
        raise ValueError(f"Unknown sparse embedder provider: {provider}")
    return spec
