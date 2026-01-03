"""Content processors for destination-specific entity preparation.

Processors implement the ContentProcessor protocol and are provided by
destinations via get_content_processor(). This inverts the dependency -
destinations declare what they need rather than handlers guessing.

Available Processors:
- ChunkEmbedProcessor: Full pipeline (text → chunks → embeddings) for Qdrant/Pinecone
- TextOnlyProcessor: Text extraction only, destination embeds (Vespa)
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
