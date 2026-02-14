"""Integration credential repository -- wraps crud.integration_credential.

Thin data-access layer providing a mockable interface for credential persistence.
All callers that need integration_credential DB operations should migrate here.
"""

from typing import Any, Optional

from airweave import crud, schemas


class IntegrationCredentialRepository:
    """Repository wrapping crud.integration_credential for testability."""

    async def create(self, db: Any, *, obj_in: Any, ctx: Any, uow: Any) -> Any:
        """Create an integration credential record."""
        return await crud.integration_credential.create(db, obj_in=obj_in, ctx=ctx, uow=uow)

    async def get(self, db: Any, *, id: Any, ctx: Any) -> Optional[Any]:
        """Get an integration credential by ID."""
        return await crud.integration_credential.get(db, id=id, ctx=ctx)

    async def update(self, db: Any, *, db_obj: Any, obj_in: Any, ctx: Any, uow: Any) -> Any:
        """Update an integration credential."""
        return await crud.integration_credential.update(
            db, db_obj=db_obj, obj_in=obj_in, ctx=ctx, uow=uow
        )
