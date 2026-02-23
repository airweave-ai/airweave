"""Fake embedder implementations for tests."""

from airweave.domains.embedders.fakes.service import (
    FakeDenseEmbedder,
    FakeEmbedderService,
    FakeSparseEmbedder,
)

__all__ = [
    "FakeDenseEmbedder",
    "FakeEmbedderService",
    "FakeSparseEmbedder",
]
