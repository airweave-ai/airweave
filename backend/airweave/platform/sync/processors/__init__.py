"""Content processors for destination-specific entity preparation.

Processors implement the ContentProcessor protocol and are provided by
destinations via get_content_processor(). This inverts the dependency -
destinations declare what they need rather than handlers guessing.

Available Processors:
- QdrantChunkEmbedProcessor: Full pipeline (text → chunks → embeddings) for Qdrant/Pinecone
- VespaChunkEmbedProcessor: Chunks + embeddings as arrays for Vespa (entity-as-document)
- TextOnlyProcessor: Text extraction only (legacy)
- RawProcessor: No processing, raw entities (S3)
"""

from .protocol import ContentProcessor
from .qdrant_chunk_embed import QdrantChunkEmbedProcessor
from .raw import RawProcessor
from .text_only import TextOnlyProcessor
from .vespa_chunk_embed import VespaChunkEmbedProcessor

__all__ = [
    "ContentProcessor",
    "QdrantChunkEmbedProcessor",
    "VespaChunkEmbedProcessor",
    "TextOnlyProcessor",
    "RawProcessor",
]
