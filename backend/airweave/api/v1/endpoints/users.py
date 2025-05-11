"""The API module that contains the endpoints for users.

Important: this module is co-responsible with the CRUD layer for secure transactions with the
database, as it contains the endpoints for user creation and retrieval.
"""

from typing import Optional

from fastapi import Depends, HTTPException
from fastapi_auth0 import Auth0User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.auth import auth0
from airweave.api.router import TrailingSlashRouter
from airweave.core.logging import logger
from airweave.models.organization import Organization as OrganizationModel
from airweave.schemas import Organization, User

router = TrailingSlashRouter()


@router.get("/", response_model=User)
async def read_user(
    *,
    current_user: User = Depends(deps.get_user),
) -> schemas.User:
    """Get current user.

    Args:
    ----
        current_user (User): The current user.

    Returns:
    -------
        schemas.User: The user object.

    """
    return current_user


@router.get("/me/organization", response_model=Organization)
async def read_user_organization(
    *,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> schemas.Organization:
    """Get the organization of the current user.

    Args:
    ----
        db (AsyncSession): The database session.
        current_user (User): The current user.

    Returns:
    -------
        schemas.Organization: The organization object.

    Raises:
    ------
        HTTPException: If the organization is not found.
    """
    if not current_user.organization_id:
        raise HTTPException(status_code=404, detail="User has no organization associated")

    # Use direct query to bypass permission checks
    stmt = select(OrganizationModel).where(OrganizationModel.id == current_user.organization_id)
    result = await db.execute(stmt)
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Return a dict with all required fields for Organization schema
    return schemas.Organization(
        id=org.id,
        name=org.name,
        description=org.description or "",
        created_at=org.created_at,
        modified_at=org.modified_at,
    )


@router.post("/create_or_update", response_model=User)
async def create_or_update_user(
    user_data: schemas.UserCreate,
    db: AsyncSession = Depends(deps.get_db),
    auth0_user: Optional[Auth0User] = Depends(auth0.get_user),
) -> schemas.User:
    """Create new user in database if it does not exist.

    Can only create user with the same email as the authenticated user.

    Args:
        user_data (schemas.UserCreate): The user object to be created.
        db (AsyncSession): Database session dependency to handle database operations.
        auth0_user (Auth0User): Authenticated auth0 user.

    Returns:
        schemas.User: The created user object.

    Raises:
        HTTPException: If the user is not authorized to create this user.
    """
    if user_data.email != auth0_user.email:
        logger.error(f"User {user_data.email} is not authorized to create user {auth0_user.email}")
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to create this user.",
        )

    user = await crud.user.get_by_email(db, email=user_data.email)

    if user:
        return user

    user = await crud.user.create(db, obj_in=user_data)
    return user
