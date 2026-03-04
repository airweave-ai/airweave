"""Protocols for collection domain."""

from typing import List, Optional, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.collection import Collection
from airweave.models.vector_db_deployment_metadata import VectorDbDeploymentMetadata


class CollectionRepositoryProtocol(Protocol):
    """Data access for collection records."""

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[Collection]:
        """Get a collection by ID within an organization."""
        ...

    async def get_by_readable_id(
        self, db: AsyncSession, readable_id: str, ctx: ApiContext
    ) -> Optional[Collection]:
        """Get a collection by human-readable ID within an organization."""
        ...

    async def get_multi(
        self,
        db: AsyncSession,
        *,
        ctx: ApiContext,
        skip: int = 0,
        limit: int = 100,
        search_query: Optional[str] = None,
    ) -> List[Collection]:
        """Get multiple collections with pagination and optional search."""
        ...

    async def count(
        self, db: AsyncSession, *, ctx: ApiContext, search_query: Optional[str] = None
    ) -> int:
        """Get total count of collections with optional search filter."""
        ...

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: dict,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> Collection:
        """Create a new collection."""
        ...

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: Collection,
        obj_in: schemas.CollectionUpdate,
        ctx: ApiContext,
    ) -> Collection:
        """Update an existing collection."""
        ...

    async def remove(self, db: AsyncSession, *, id: UUID, ctx: ApiContext) -> Optional[Collection]:
        """Delete a collection by ID."""
        ...


class VectorDbDeploymentMetadataRepositoryProtocol(Protocol):
    """Data access for the singleton VectorDbDeploymentMetadata row."""

    async def get(self, db: AsyncSession) -> VectorDbDeploymentMetadata:
        """Return the single VectorDbDeploymentMetadata row (created at startup)."""
        ...


class CollectionServiceProtocol(Protocol):
    """Service for collection lifecycle operations."""

    async def list(
        self,
        db: AsyncSession,
        *,
        ctx: ApiContext,
        skip: int = 0,
        limit: int = 100,
        search_query: Optional[str] = None,
    ) -> List[schemas.Collection]:
        """List collections with pagination and optional search."""
        ...

    async def count(
        self, db: AsyncSession, *, ctx: ApiContext, search_query: Optional[str] = None
    ) -> int:
        """Get total count of collections."""
        ...

    async def create(
        self,
        db: AsyncSession,
        *,
        collection_in: schemas.CollectionCreate,
        ctx: ApiContext,
    ) -> schemas.Collection:
        """Create a new collection."""
        ...

    async def get(
        self, db: AsyncSession, *, readable_id: str, ctx: ApiContext
    ) -> schemas.Collection:
        """Get a collection by readable ID."""
        ...

    async def update(
        self,
        db: AsyncSession,
        *,
        readable_id: str,
        collection_in: schemas.CollectionUpdate,
        ctx: ApiContext,
    ) -> schemas.Collection:
        """Update a collection."""
        ...

    async def delete(
        self, db: AsyncSession, *, readable_id: str, ctx: ApiContext
    ) -> schemas.Collection:
        """Delete a collection and all related data."""
        ...
