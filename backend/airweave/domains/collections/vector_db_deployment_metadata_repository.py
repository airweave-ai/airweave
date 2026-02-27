"""Repository for the singleton VectorDbDeploymentMetadata row."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.domains.collections.protocols import VectorDbDeploymentMetadataRepositoryProtocol
from airweave.models.vector_db_deployment_metadata import VectorDbDeploymentMetadata


class VectorDbDeploymentMetadataRepository(VectorDbDeploymentMetadataRepositoryProtocol):
    """Queries the single VectorDbDeploymentMetadata row."""

    async def get(self, db: AsyncSession) -> VectorDbDeploymentMetadata:
        """Return the single VectorDbDeploymentMetadata row (created at startup)."""
        result = await db.execute(select(VectorDbDeploymentMetadata).limit(1))
        return result.scalar_one()
