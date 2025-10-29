"""The API module that contains the endpoints for users.

Important: this module is co-responsible with the CRUD layer for secure transactions with the
database, as it contains the endpoints for user creation and retrieval.
"""

from typing import List, Optional
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, HTTPException
from fastapi_auth0 import Auth0User
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.analytics import business_events
from airweave.api import deps
from airweave.api.auth import auth0
from airweave.api.context import ApiContext
from airweave.api.router import TrailingSlashRouter
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod
from airweave.db.unit_of_work import UnitOfWork
from airweave.email.services import send_welcome_email
from airweave.schemas import OrganizationWithRole, User

router = TrailingSlashRouter()


@router.get("/", response_model=User)
async def read_user(
    *,
    current_user: schemas.User = Depends(deps.get_user),
) -> schemas.User:
    """Get current user with all organization relationships.

    Args:
    ----
        current_user (schemas.User): The authenticated user.

    Returns:
    -------
        schemas.User: The user object with all organization data.

    """
    return current_user


@router.get("/me/organizations", response_model=List[OrganizationWithRole])
async def read_user_organizations(
    *,
    db: AsyncSession = Depends(deps.get_db),
    current_user: schemas.User = Depends(deps.get_user),
) -> List[OrganizationWithRole]:
    """Get all organizations that the current user is a member of.

    Args:
    ----
        db: Database session
        current_user (schemas.User): The authenticated user.

    Returns:
    -------
        List[OrganizationWithRole]: List of organizations with the user's role and primary status.

    """
    # Use CRUD method which properly loads feature_flags
    return await crud.organization.get_user_organizations_with_roles(db=db, user_id=current_user.id)


@router.post("/create_or_update", response_model=User)
async def create_or_update_user(
    user_data: schemas.UserCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(deps.get_db),
    auth0_user: Optional[Auth0User] = Depends(auth0.get_user),
) -> schemas.User:
    """Create new user in database if it does not exist, with Auth0 organization sync.

    Can only create user with the same email as the authenticated user.
    Integrates with Auth0 Organizations API to sync user organizations.

    Args:
        user_data (schemas.UserCreate): The user object to be created.
        background_tasks (BackgroundTasks): FastAPI background tasks for non-blocking operations.
        db (AsyncSession): Database session dependency to handle database operations.
        auth0_user (Auth0User): Authenticated auth0 user.

    Returns:
        schemas.User: The created user object with organization relationships.

    Raises:
        HTTPException: If the user is not authorized to create this user.
        HTTPException: If a user with the same email but different auth0_id already exists.
    """
    if user_data.email != auth0_user.email:
        logger.error(f"User {user_data.email} is not authorized to create user {auth0_user.email}")
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to create this user.",
        )

    existing_user = None

    # Check if user already exists
    try:
        existing_user = await crud.user.get_by_email(db, email=user_data.email)
    except NotFoundException:
        logger.info(f"User {user_data.email} not found, creating...")

    if existing_user:
        # Check for Auth0 ID conflicts
        incoming_auth0_id = auth0_user.id if auth0_user else user_data.auth0_id

        if (
            existing_user.auth0_id
            and incoming_auth0_id
            and existing_user.auth0_id != incoming_auth0_id
        ):
            logger.warning(
                f"Auth0 ID conflict for user {user_data.email}: "
                f"existing={existing_user.auth0_id}, incoming={incoming_auth0_id}"
            )
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "auth0_id_conflict",
                    "message": "A user with this email already exists but with a different "
                    "Auth0 ID. This typically happens when you use a different authentication "
                    "method to sign up for Airweave. Please contact support for assistance.",
                },
            )

        # User exists and no conflict - sync their Auth0 organizations
        from airweave.core.organization_service import OrganizationService

        organization_service = OrganizationService()
        try:
            updated_user = await organization_service.sync_user_organizations(db, existing_user)
            logger.info(f"Synced Auth0 organizations for existing user: {user_data.email}")
            return schemas.User.model_validate(updated_user)
        except Exception as e:
            logger.warning(f"Failed to sync Auth0 organizations for user {user_data.email}: {e}")
            return schemas.User.model_validate(existing_user)

    # New user - handle signup with Auth0 organization sync
    from airweave.core.organization_service import OrganizationService

    organization_service = OrganizationService()

    try:
        # Add auth0_id to user data if available
        user_dict = user_data.model_dump()
        if auth0_user:
            user_dict["auth0_id"] = auth0_user.id

        # Handle new user signup with Auth0 integration
        user = await organization_service.handle_new_user_signup(db, user_dict, create_org=False)

        logger.info(f"Created new user {user.email}.")

        # Track user creation with business events
        try:
            business_events.track_user_created(
                user_id=user.id,
                email=user.email,
                full_name=user.full_name,
                auth0_id=user.auth0_id,
                signup_source="auth0",
            )
        except Exception as e:
            logger.warning(f"Failed to track user creation analytics: {e}")

        # Send welcome email in background to avoid blocking the response
        background_tasks.add_task(send_welcome_email, user.email, user.full_name or user.email)

        return schemas.User.model_validate(user)

    except Exception as e:
        logger.error(f"Failed to create user with Auth0 integration: {e}")
        # Fallback to traditional user creation
        async with UnitOfWork(db) as uow:
            user, organization = await crud.user.create_with_organization(
                db, obj_in=user_data, uow=uow
            )
            _ = await crud.api_key.create(
                db,
                obj_in=schemas.APIKeyCreate(name="Default API Key"),
                ctx=ApiContext(
                    request=uuid4(),
                    user=user,
                    organization=organization,
                    auth_method=AuthMethod.AUTH0,
                ),
                uow=uow,
            )
        logger.info(f"Created user {user.email} with fallback method")

        # Send welcome email in background to avoid blocking the response
        background_tasks.add_task(send_welcome_email, user.email, user.full_name or user.email)

        return user
