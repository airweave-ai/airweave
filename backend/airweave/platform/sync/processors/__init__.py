"""Content processors for entity preparation.

Available Processors:
- ChunkEmbedProcessor: Unified processor for chunk-as-document model (Qdrant, Vespa)
  - With sparse=True: dense + sparse embeddings for hybrid search (Qdrant)
  - With sparse=False: dense only, BM25 computed server-side (Vespa)
"""

from .chunk_embed import ChunkEmbedProcessor

__all__ = [
    "ChunkEmbedProcessor",
]
