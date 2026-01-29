"""Retrieval strategy schemas for spotlight search."""

from enum import Enum


class SpotlightRetrievalStrategy(str, Enum):
    """Supported retrieval strategies."""

    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    HYBRID = "hybrid"
