"""Embedders for dense and sparse vector computation."""

from .fastembed import SparseEmbedder
from .openai import DenseEmbedder

__all__ = ["DenseEmbedder", "SparseEmbedder"]
