"""Fake VectorDbDeploymentMetadata repository for testing."""

from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.domains.embedders.config import (
    DENSE_EMBEDDER,
    EMBEDDING_DIMENSIONS,
    SPARSE_EMBEDDER,
)
from airweave.models.vector_db_deployment_metadata import VectorDbDeploymentMetadata


class FakeVectorDbDeploymentMetadataRepository:
    """In-memory fake that returns a deterministic VectorDbDeploymentMetadata mock."""

    def __init__(self, *, deployment_metadata_id=None) -> None:
        """Initialize with an optional fixed ID."""
        self._id = deployment_metadata_id or uuid4()

    async def get(self, db: AsyncSession) -> VectorDbDeploymentMetadata:
        """Return a mock VectorDbDeploymentMetadata with config constants."""
        vd = MagicMock(spec=VectorDbDeploymentMetadata)
        vd.id = self._id
        vd.embedding_dimensions = EMBEDDING_DIMENSIONS
        vd.dense_embedder = DENSE_EMBEDDER
        vd.sparse_embedder = SPARSE_EMBEDDER
        return vd
