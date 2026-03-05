"""Content processors for destination-specific entity preparation.

Processors implement the ContentProcessor protocol and are provided by
destinations via get_content_processor(). This inverts the dependency -
destinations declare what they need rather than handlers guessing.

Available Processors:
- ChunkEmbedProcessor: Unified processor for chunk-as-document model (Qdrant, Vespa)
  - With sparse=True: dense + sparse embeddings for hybrid search (Qdrant)
  - With sparse=False: dense only, BM25 computed server-side (Vespa)
- TextOnlyProcessor: Text extraction only (legacy)
- RawProcessor: No processing, raw entities (S3)
"""

from .chunk_embed import ChunkEmbedProcessor
from .protocol import ContentProcessor
from .raw import RawProcessor
from .text_only import TextOnlyProcessor

__all__ = [
    "ContentProcessor",
    "ChunkEmbedProcessor",
    "TextOnlyProcessor",
    "RawProcessor",
]
