"""Initialize the database with the first superuser."""

import datetime
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core.config import settings
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod
from airweave.db.init_db_native import init_db_with_native_connections


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

        # Grant superuser privileges at DB level for admin operations and tests
        from airweave.models.user import User as UserModel

        db_user = await db.get(UserModel, user.id)
        if db_user:
            db_user.is_superuser = True
            db.add(db_user)
            await db.commit()
            await db.refresh(db_user)

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
                organization=organization,
                auth_method=AuthMethod.SYSTEM,
                logger=logger,
            ),
        )
