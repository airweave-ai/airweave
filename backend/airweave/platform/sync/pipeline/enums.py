"""Enums for the sync pipeline."""

from enum import Enum


class ProcessingRequirement(Enum):
    """What processing a destination expects from Airweave.

    This enum determines how the sync pipeline processes entities before
    sending them to the destination. The DestinationHandler maps these
    to the appropriate processor.

    CHUNKS_AND_EMBEDDINGS: Full processing for vector databases (Qdrant, Vespa)
    - Chunks text using semantic/AST chunking
    - Computes dense embeddings (3072-dim) for neural/semantic search
    - Computes sparse embeddings (FastEmbed Qdrant/bm25) for keyword search scoring
    """

    CHUNKS_AND_EMBEDDINGS = "chunks_and_embeddings"
    TEXT_ONLY = "text_only"
    RAW = "raw"
