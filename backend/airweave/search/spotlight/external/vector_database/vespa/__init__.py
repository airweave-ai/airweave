"""Vespa vector database integration for spotlight search."""

from airweave.search.spotlight.external.vector_database.vespa.client import (
    VespaVectorDB,
)
from airweave.search.spotlight.external.vector_database.vespa.filter_translator import (
    FilterTranslationError,
)

__all__ = ["VespaVectorDB", "FilterTranslationError"]
