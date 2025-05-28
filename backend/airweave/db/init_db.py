"""Initialize the database with the first superuser."""

import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.config import settings
from airweave.db.init_db_native import init_db_with_native_connections


async def init_db(db: AsyncSession) -> None:
    """Initialize the database with the first organization and superuser.

    Args:
    ----
        db (AsyncSession): The database session.
    """
    # First initialize native connections
    await init_db_with_native_connections(db)

    organization = await crud.organization.get_by_name(db, name=settings.FIRST_SUPERUSER)
    if not organization:
        organization_in = schemas.OrganizationCreate(
            name=settings.FIRST_SUPERUSER,
            description="Superuser organization",
        )
        organization = await crud.organization.create(db, obj_in=organization_in)

    user = await crud.user.get_by_email(db, email=settings.FIRST_SUPERUSER)

    if not user:
        user_in = schemas.UserCreate(
            email=settings.FIRST_SUPERUSER,
            full_name="Superuser",
            password=settings.FIRST_SUPERUSER_PASSWORD,
            organization_id=organization.id,
        )
        user = await crud.user.create(db, obj_in=user_in)
        _ = await crud.api_key.create_with_user(
            db,
            obj_in=schemas.APIKeyCreate(
                user_id=user.id,
                name="Superuser API Key",
                description="Superuser API Key",
                expires_at=datetime.datetime.now() + datetime.timedelta(days=365),
            ),
            current_user=user,
        )
