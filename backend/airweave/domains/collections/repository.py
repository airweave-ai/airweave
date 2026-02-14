"""Collection repository -- wraps crud.collection.

Only includes methods source connections currently needs.
"""

from typing import Any, Optional

from airweave import crud


class CollectionRepository:
    """Repository wrapping crud.collection."""

    async def get_by_readable_id(self, db: Any, *, readable_id: str, ctx: Any) -> Optional[Any]:
        """Get a collection by readable ID."""
        return await crud.collection.get_by_readable_id(db, readable_id=readable_id, ctx=ctx)
