"""Initialize the database with the first superuser."""

import datetime
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.util.concurrency import greenlet_spawn

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core.config import settings
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import logger
from airweave.db.init_db_native import init_db_with_native_connections

async def init_db_with_greenlet(db: AsyncSession):
    await greenlet_spawn(init_db, db)
    
async def init_db(db: AsyncSession) -> None:
    """Initialize the database with the first organization and superuser.

    Args:
    ----
        db (AsyncSession): The database session.
    """
    # First initialize native connections
    await init_db_with_native_connections(db)
    try:
        user = await crud.user.get_by_email(db, email=settings.FIRST_SUPERUSER)
    except NotFoundException:
        logger.info(f"User {settings.FIRST_SUPERUSER} not found, creating...")
        user_in = schemas.UserCreate(
            email=settings.FIRST_SUPERUSER,
            full_name="Superuser",
            password=settings.FIRST_SUPERUSER_PASSWORD,
        )
        user, organization = await crud.user.create_with_organization(db, obj_in=user_in)
        _ = await crud.api_key.create(
            db,
            obj_in=schemas.APIKeyCreate(
                user_id=user.id,
                name="Superuser API Key",
                description="Superuser API Key",
                expires_at=datetime.datetime.now() + datetime.timedelta(days=365),
            ),
            ctx=ApiContext(
                request_id=str(uuid.uuid4()),
                user=user,
                organization_id=organization.id,
                auth_method="system",
                logger=logger,
            ),
        )
