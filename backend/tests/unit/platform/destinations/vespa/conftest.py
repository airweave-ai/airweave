"""Pytest fixtures for Vespa destination tests."""

import pytest
from uuid import UUID

from airweave.platform.destinations.vespa.filter_translator import FilterTranslator
from airweave.platform.destinations.vespa.query_builder import QueryBuilder


@pytest.fixture
def filter_translator():
    """Create a FilterTranslator instance."""
    return FilterTranslator()


@pytest.fixture
def query_builder():
    """Create a QueryBuilder instance."""
    return QueryBuilder()


@pytest.fixture
def sample_collection_id():
    """Sample collection UUID for testing."""
    return UUID("12345678-1234-1234-1234-123456789abc")


@pytest.fixture
def sample_dense_embeddings():
    """Sample dense embeddings (3072-dim)."""
    return [[0.1] * 3072, [0.2] * 3072]


@pytest.fixture
def sample_sparse_embedding():
    """Sample sparse embedding object."""
    class MockSparseEmbedding:
        def __init__(self):
            self.indices = [0, 5, 10, 15]
            self.values = [0.8, 0.6, 0.4, 0.2]
    
    return MockSparseEmbedding()

