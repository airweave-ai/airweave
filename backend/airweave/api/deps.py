"""Dependencies that are used in the API endpoints."""

from typing import Optional

from fastapi import Depends, Header, HTTPException
from fastapi_auth0 import Auth0User
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.auth import auth0
from airweave.core.config import settings
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import logger
from airweave.db.session import get_db


async def get_user(
    db: AsyncSession = Depends(get_db),
    x_api_key: Optional[str] = Header(None),
    auth0_user: Optional[Auth0User] = Depends(auth0.get_user),
) -> schemas.User:
    """Retrieve user from super user from database.

    Args:
    ----
        request (Request): The request object.
        db (AsyncSession): Database session.
        x_api_key (Optional[str]): API key provided in the request header.
        auth0_user (Optional[Auth0User]): User details from Auth0.

    Returns:
    -------
        schemas.User: User details from the database.

    Raises:
    ------
        HTTPException: If the user is not found in the database or if
            no authentication method is provided.

    """
    # For test environments or when auth is disabled, use the first superuser
    if not settings.AUTH_ENABLED:
        user = await crud.user.get_by_email(db, email=settings.FIRST_SUPERUSER)
        return schemas.User.model_validate(user)

    if auth0_user:
        user = await crud.user.get_by_email(db, email=auth0_user.email)
        return schemas.User.model_validate(user)

    if x_api_key:
        user = await crud.user.get_by_api_key(db, api_key=x_api_key)
        return schemas.User.model_validate(user)

    raise HTTPException(status_code=401, detail="Unauthorized, no user was found")


async def get_user_from_api_key(db: AsyncSession, api_key: str) -> schemas.User:
    """Retrieve user from database using the API key.

    First validate the API key and then retrieve the user from the database.

    Args:
    ----
        db (AsyncSession): Database session.
        api_key (str): The API key.

    Returns:
    -------
        schemas.User: User details from the database.

    Raises:
    ------
        HTTPException: If the user is not found in the database or the API key is invalid.

    """
    try:
        api_key_obj = await crud.api_key.get_by_key(db, key=api_key)
    except ValueError as e:
        logger.error(f"Error retrieving API key: {e}", exc_info=True)
        if "expired" in str(e):
            raise HTTPException(status_code=403, detail="API key has expired") from e
        raise HTTPException(status_code=403, detail="Invalid API key") from e
    except NotFoundException as e:
        logger.error(f"API key not found: {e}", exc_info=True)
        raise HTTPException(status_code=403, detail="API key not found") from e
    user = api_key_obj.created_by
    return schemas.User.model_validate(user)


# Add this function to authenticate users with a token directly
async def get_user_from_token(token: str, db: AsyncSession) -> Optional[schemas.User]:
    """Verify the token and return the corresponding user.

    Args:
        token: The authentication token.
        db: The database session.

    Returns:
        The user if authentication succeeds, None otherwise.
    """
    try:
        # Remove 'Bearer ' prefix if present
        if token.startswith("Bearer "):
            token = token[7:]

        # If auth is disabled, just use the first superuser
        if not settings.AUTH_ENABLED:
            user = await crud.user.get_by_email(db, email=settings.FIRST_SUPERUSER)
            return schemas.User.model_validate(user)

        # Get user ID from the token using the auth module
        from airweave.api.auth import get_user_from_token as auth_get_user

        auth0_user = await auth_get_user(token)
        if not auth0_user:
            return None

        # Get the internal user representation
        user = await crud.user.get_by_email(db=db, email=auth0_user.email)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except Exception as e:
        logger.error(f"Error in get_user_from_token: {e}")
        return None
