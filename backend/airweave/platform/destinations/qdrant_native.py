"""Qdrant native destination implementation."""

from airweave.platform.decorators import destination
from airweave.platform.destinations.qdrant import QdrantDestination


@destination("Qdrant Native", "qdrant_native", labels=["Vector"])
class QdrantNativeDestination(QdrantDestination):
    """Qdrant native destination implementation."""
