"""Manual registration data for embedder models.

This is the single source of truth for all known embedder models.
Add new models here — the domain registry reads this at startup.
"""

from dataclasses import dataclass

from airweave.domains.embedders.dense.local import LocalDenseEmbedder
from airweave.domains.embedders.dense.mistral import MistralDenseEmbedder
from airweave.domains.embedders.dense.openai import OpenAIDenseEmbedder
from airweave.domains.embedders.sparse.fastembed import FastEmbedSparseEmbedder


@dataclass(frozen=True)
class DenseEmbedderSpec:
    """Specification for registering a dense embedding model."""

    short_name: str
    name: str
    description: str
    provider: str
    api_model_name: str
    max_dimensions: int
    max_tokens: int
    supports_matryoshka: bool
    embedder_class: type
    required_setting: str | None


@dataclass(frozen=True)
class SparseEmbedderSpec:
    """Specification for registering a sparse embedding model."""

    short_name: str
    name: str
    description: str
    provider: str
    api_model_name: str
    embedder_class: type
    required_setting: str | None


DENSE_EMBEDDERS: list[DenseEmbedderSpec] = [
    DenseEmbedderSpec(
        short_name="openai_text_embedding_3_small",
        name="OpenAI text-embedding-3-small",
        description="OpenAI small embedding model with Matryoshka support (up to 1536d)",
        provider="openai",
        api_model_name="text-embedding-3-small",
        max_dimensions=1536,
        max_tokens=8192,
        supports_matryoshka=True,
        embedder_class=OpenAIDenseEmbedder,
        required_setting="OPENAI_API_KEY",
    ),
    DenseEmbedderSpec(
        short_name="openai_text_embedding_3_large",
        name="OpenAI text-embedding-3-large",
        description="OpenAI large embedding model with Matryoshka support (up to 3072d)",
        provider="openai",
        api_model_name="text-embedding-3-large",
        max_dimensions=3072,
        max_tokens=8192,
        supports_matryoshka=True,
        embedder_class=OpenAIDenseEmbedder,
        required_setting="OPENAI_API_KEY",
    ),
    DenseEmbedderSpec(
        short_name="mistral_embed",
        name="Mistral Embed",
        description="Mistral embedding model with fixed 1024 dimensions",
        provider="mistral",
        api_model_name="mistral-embed",
        max_dimensions=1024,
        max_tokens=8192,
        supports_matryoshka=False,
        embedder_class=MistralDenseEmbedder,
        required_setting="MISTRAL_API_KEY",
    ),
    DenseEmbedderSpec(
        short_name="local_minilm",
        name="Local MiniLM-L6-v2",
        description="Local sentence-transformers model via text2vec container (384d)",
        provider="local",
        api_model_name="sentence-transformers/all-MiniLM-L6-v2",
        max_dimensions=384,
        max_tokens=512,
        supports_matryoshka=False,
        embedder_class=LocalDenseEmbedder,
        required_setting="TEXT2VEC_INFERENCE_URL",
    ),
]

SPARSE_EMBEDDERS: list[SparseEmbedderSpec] = [
    SparseEmbedderSpec(
        short_name="fastembed_bm25",
        name="FastEmbed BM25",
        description="Sparse BM25 embeddings via FastEmbed (Qdrant/bm25 model)",
        provider="fastembed",
        api_model_name="Qdrant/bm25",
        embedder_class=FastEmbedSparseEmbedder,
        required_setting=None,
    ),
]
