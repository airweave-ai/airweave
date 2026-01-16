"""Enums for the sync pipeline."""

from enum import Enum


class ProcessingRequirement(Enum):
    """What processing a destination expects from Airweave.

    This enum determines how the sync pipeline processes entities before
    sending them to the destination. The DestinationHandler maps these
    to the appropriate processor.

    Both CHUNKS_AND_EMBEDDINGS and CHUNKS_AND_EMBEDDINGS_DENSE_ONLY use
    the same ChunkEmbedProcessor, but with different sparse embedding settings:
    - CHUNKS_AND_EMBEDDINGS: dense + sparse (for Qdrant hybrid search)
    - CHUNKS_AND_EMBEDDINGS_DENSE_ONLY: dense only (for Vespa, BM25 computed server-side)
    """

    CHUNKS_AND_EMBEDDINGS = "chunks_and_embeddings"
    CHUNKS_AND_EMBEDDINGS_DENSE_ONLY = "chunks_and_embeddings_dense_only"
    TEXT_ONLY = "text_only"
    RAW = "raw"
