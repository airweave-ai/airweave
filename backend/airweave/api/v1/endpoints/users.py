"""API endpoints for users.

Thin HTTP layer — delegates business logic to ``UserServiceProtocol``.
"""

from typing import List, Optional

from fastapi import Depends, HTTPException
from fastapi_auth0 import Auth0User
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api import deps
from airweave.api.auth import auth0
from airweave.api.deps import Inject
from airweave.api.router import TrailingSlashRouter
from airweave.core.logging import logger
from airweave.domains.users.protocols import UserServiceProtocol
from airweave.domains.users.types import is_email_authorized
from airweave.schemas import OrganizationWithRole, User

router = TrailingSlashRouter()


@router.get("/", response_model=User)
async def read_user(
    *,
    current_user: schemas.User = Depends(deps.get_user),
) -> schemas.User:
    """Get current user with all organization relationships."""
    return current_user


@router.get("/me/organizations", response_model=List[OrganizationWithRole])
async def read_user_organizations(
    *,
    db: AsyncSession = Depends(deps.get_db),
    current_user: schemas.User = Depends(deps.get_user),
    user_service: UserServiceProtocol = Inject(UserServiceProtocol),
) -> List[OrganizationWithRole]:
    """Get all organizations that the current user is a member of."""
    return await user_service.get_user_organizations(db, user_id=current_user.id)


@router.post("/create_or_update", response_model=User)
async def create_or_update_user(
    user_data: schemas.UserCreate,
    db: AsyncSession = Depends(deps.get_db),
    auth0_user: Optional[Auth0User] = Depends(auth0.get_user),
    user_service: UserServiceProtocol = Inject(UserServiceProtocol),
) -> schemas.User:
    """Create new user or sync existing user's Auth0 organizations.

    Can only create user with the same email as the authenticated user.
    """
    auth0_email = auth0_user.email if auth0_user else None
    if not auth0_email or not is_email_authorized(user_data.email, auth0_email):
        logger.error(f"User {user_data.email} is not authorized to create user {auth0_email}")
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to create this user.",
        )

    result = await user_service.create_or_update(db, user_data, auth0_user)
    return result.user
