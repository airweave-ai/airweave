"""Retrieval strategy schemas for agentic search."""

from enum import Enum


class AgenticSearchRetrievalStrategy(str, Enum):
    """Supported retrieval strategies."""

    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    HYBRID = "hybrid"
