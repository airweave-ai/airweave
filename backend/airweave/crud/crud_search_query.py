"""CRUD operations for search query models."""

from typing import List
from uuid import UUID

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.context import BaseContext
from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.models.search_query import SearchQuery
from airweave.schemas.search_query import SearchQueryCreate, SearchQueryUpdate


class CRUDSearchQuery(CRUDBaseOrganization[SearchQuery, SearchQueryCreate, SearchQueryUpdate]):
    """CRUD operations for search query persistence."""

    async def get_user_search_history(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        collection_id: UUID,
        ctx: BaseContext,
        limit: int = 50,
        offset: int = 0,
    ) -> List[SearchQuery]:
        """Get search history for a specific user within a specific collection.

        Args:
            db: Database session
            user_id: ID of the user
            collection_id: ID of the collection to get search history for
            ctx: API context
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            List of search queries for the user in the specified collection
        """
        query = (
            select(SearchQuery)
            .where(
                and_(
                    SearchQuery.organization_id == ctx.organization.id,
                    SearchQuery.user_id == user_id,
                    SearchQuery.collection_id == collection_id,
                )
            )
            .order_by(desc(SearchQuery.created_at))
            .offset(offset)
            .limit(limit)
        )

        result = await db.execute(query)
        return list(result.unique().scalars().all())


# Create singleton instance
search_query = CRUDSearchQuery(SearchQuery)
