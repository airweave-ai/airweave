"""Dependencies that are used in the API endpoints."""

import uuid
from typing import Optional, Tuple

from fastapi import Depends, Header, HTTPException, Request
from fastapi_auth0 import Auth0User
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.auth import auth0
from airweave.api.context import ApiContext
from airweave.core.config import settings
from airweave.core.context_cache_service import context_cache
from airweave.core.exceptions import NotFoundException, RateLimitExceededException
from airweave.core.guard_rail_service import GuardRailService
from airweave.core.logging import ContextualLogger, logger
from airweave.core.rate_limiter_service import RateLimiter
from airweave.db.session import get_db
from airweave.schemas.rate_limit import RateLimitResult


async def _authenticate_system_user(db: AsyncSession) -> Tuple[Optional[schemas.User], str, dict]:
    """Authenticate system user when auth is disabled."""
    user = await crud.user.get_by_email(db, email=settings.FIRST_SUPERUSER)
    if user:
        user_context = schemas.User.model_validate(user)
        return user_context, "system", {"disabled_auth": True}
    return None, "", {}


async def _authenticate_auth0_user(
    db: AsyncSession, auth0_user: Auth0User
) -> Tuple[Optional[schemas.User], str, dict]:
    """Authenticate Auth0 user."""
    try:
        user = await crud.user.get_by_email(db, email=auth0_user.email)
    except NotFoundException:
        logger.error(f"User {auth0_user.email} not found in database")
        return None, "", {}
    user_context = schemas.User.model_validate(user)
    return user_context, "auth0", {"auth0_id": auth0_user.id}


async def _authenticate_api_key(db: AsyncSession, api_key: str) -> Tuple[None, str, dict, str]:
    """Authenticate API key and return organization ID.

    Uses Redis cache for API key → org_id mapping to avoid DB lookup on every request.
    The 10-minute cache TTL provides sufficient protection against expired keys.

    Returns:
        Tuple of (user_context, auth_method, auth_metadata, organization_id)
    """
    try:
        # Try cache first for API key → org_id mapping
        org_id = await context_cache.get_api_key_org_id(api_key)

        if org_id:
            # Cache hit - use cached mapping without DB validation
            # The 10-minute TTL is sufficient; no need to check expiration on every request
            auth_metadata = {
                "api_key_id": "cached",  # We don't have the ID from cache, but it's not critical
                "created_by": None,
            }
            return None, "api_key", auth_metadata, str(org_id)

        # Cache miss - validate API key via CRUD
        api_key_obj = await crud.api_key.get_by_key(db, key=api_key)
        org_id = api_key_obj.organization_id

        # Cache the mapping for next time
        await context_cache.set_api_key_org_id(api_key, org_id)

        auth_metadata = {
            "api_key_id": str(api_key_obj.id),
            "created_by": api_key_obj.created_by_email,
        }

        return None, "api_key", auth_metadata, str(org_id)

    except (ValueError, NotFoundException) as e:
        logger.error(f"API key validation failed: {e}")
        if "expired" in str(e):
            raise HTTPException(status_code=403, detail="API key has expired") from e
        raise HTTPException(status_code=403, detail="Invalid or expired API key") from e


def _resolve_organization_id(
    x_organization_id: Optional[str],
    user_context: Optional[schemas.User],
    auth_method: str,
    auth_metadata: dict,
    api_key_org_id: Optional[str] = None,
) -> str:
    """Resolve the organization ID from header or fallback to defaults.

    Args:
        x_organization_id: Organization ID from header
        user_context: User context (if user auth)
        auth_method: Authentication method used
        auth_metadata: Auth metadata dict
        api_key_org_id: Organization ID from API key auth (already resolved)

    Returns:
        Organization ID string
    """
    if x_organization_id:
        return x_organization_id

    # Fallback logic based on auth method
    if auth_method in ["system", "auth0"] and user_context:
        if user_context.primary_organization_id:
            return str(user_context.primary_organization_id)
    elif auth_method == "api_key" and api_key_org_id:
        return api_key_org_id

    raise HTTPException(
        status_code=400,
        detail="Organization context required (X-Organization-ID header missing)",
    )


async def _validate_organization_access(
    db: AsyncSession,
    organization_id: str,
    user_context: Optional[schemas.User],
    auth_method: str,
    x_api_key: Optional[str],
) -> None:
    """Validate that the user/API key has access to the requested organization."""
    # For user-based auth, verify the user has access to the requested organization
    if user_context and auth_method in ["auth0", "system"]:
        user_org_ids = [str(org.organization.id) for org in user_context.user_organizations]
        if organization_id not in user_org_ids:
            raise HTTPException(
                status_code=403,
                detail=f"User does not have access to organization {organization_id}",
            )

    # For API key auth, verify the API key belongs to the requested organization
    elif auth_method == "api_key" and x_api_key:
        api_key_obj = await crud.api_key.get_by_key(db, key=x_api_key)
        if str(api_key_obj.organization_id) != organization_id:
            raise HTTPException(
                status_code=403,
                detail=f"API key does not have access to organization {organization_id}",
            )


async def _get_or_fetch_user_context(
    db: AsyncSession,
    auth0_user: Auth0User,
) -> Tuple[Optional[schemas.User], str, dict]:
    """Get user context from cache or fetch from database.

    Args:
    ----
        db (AsyncSession): Database session.
        auth0_user (Auth0User): Auth0 user details.

    Returns:
    -------
        Tuple containing user context, auth method, and auth metadata.
    """
    # Try cache first for user
    user_context = await context_cache.get_user(auth0_user.email)
    if not user_context:
        # Cache miss - fetch from DB
        user_context, auth_method, auth_metadata = await _authenticate_auth0_user(db, auth0_user)
        # Cache for next time
        if user_context:
            await context_cache.set_user(user_context)
    else:
        # Cache hit - still need auth metadata
        auth_method = "auth0"
        auth_metadata = {"auth0_id": auth0_user.id}

    return user_context, auth_method, auth_metadata


async def _get_or_fetch_organization(
    db: AsyncSession,
    organization_id: str,
) -> schemas.Organization:
    """Get organization from cache or fetch from database with billing info.

    This function returns a fully enriched Organization schema with:
    - Feature flags
    - Billing information (plan, status, etc.)
    - Current billing period

    Args:
        db: Database session
        organization_id: Organization ID to fetch

    Returns:
        Enriched Organization schema object
    """
    # Try cache first for organization
    organization_schema = await context_cache.get_organization(uuid.UUID(organization_id))

    if not organization_schema:
        # Cache miss - fetch from DB with enrichment
        # The CRUD method returns enriched schemas.Organization with billing and current period
        organization_schema = await crud.organization.get(
            db, id=organization_id, skip_access_validation=True, enrich=True
        )

        # Cache the enriched organization for next time
        await context_cache.set_organization(organization_schema)

    return organization_schema


async def _check_and_enforce_rate_limit(
    request: Request,
    ctx: ApiContext,
) -> None:
    """Check and enforce rate limits for the organization.

    Stores RateLimitResult in request.state for middleware to add headers.

    Args:
    ----
        request (Request): The FastAPI request object to store rate limit info.
        ctx (ApiContext): API context containing organization and logger.

    Raises:
    ------
        RateLimitExceededException: If rate limit is exceeded.
    """
    try:
        result = await RateLimiter.check_rate_limit(ctx)
        # Store the full result object for middleware
        request.state.rate_limit_result = result

    except RateLimitExceededException:
        # Re-raise rate limit exceptions to be handled by exception handler
        raise
    except Exception as e:
        logger.error(f"Rate limit check failed: {e}. Allowing request.")

        request.state.rate_limit_result = RateLimitResult(
            allowed=True,
            retry_after=0.0,
            limit=0,
            remaining=9999,
        )


async def get_context(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_organization_id: Optional[str] = Header(None, alias="X-Organization-ID"),
    auth0_user: Optional[Auth0User] = Depends(auth0.get_user),
) -> ApiContext:
    """Create unified API context for the request.

    This is the primary dependency for all API endpoints, providing:
    - Request tracking (request_id)
    - The API context (user, organization, auth method)
    - Pre-configured contextual logger with all dimensions

    Args:
    ----
        request (Request): The FastAPI request object.
        db (AsyncSession): Database session.
        x_api_key (Optional[str]): API key provided in the request header.
        x_organization_id (Optional[str]): Organization ID provided in the X-Organization-ID header.
        auth0_user (Optional[Auth0User]): User details from Auth0.

    Returns:
    -------
        ApiContext: Unified API context with auth and logging.

    Raises:
    ------
        HTTPException: If no valid auth method is provided or org access is denied.
    """
    # Get request ID from middleware
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    # Perform authentication (reuse existing logic)
    user_context = None
    auth_method = ""
    auth_metadata = {}
    api_key_org_id = None  # For API key auth, this is already resolved

    # Determine authentication method and context
    if not settings.AUTH_ENABLED:
        user_context, auth_method, auth_metadata = await _authenticate_system_user(db)
    elif auth0_user:
        user_context, auth_method, auth_metadata = await _get_or_fetch_user_context(db, auth0_user)
    elif x_api_key:
        user_context, auth_method, auth_metadata, api_key_org_id = await _authenticate_api_key(
            db, x_api_key
        )

    if not auth_method:
        raise HTTPException(status_code=401, detail="No valid authentication provided")

    organization_id = _resolve_organization_id(
        x_organization_id, user_context, auth_method, auth_metadata, api_key_org_id
    )

    organization_schema = await _get_or_fetch_organization(db, organization_id)

    await _validate_organization_access(db, organization_id, user_context, auth_method, x_api_key)

    base_logger = logger.with_context(
        request_id=request_id,
        organization_id=str(organization_schema.id),
        organization_name=organization_schema.name,
        auth_method=auth_method,
        context_base="api",
    )

    # Add user context if available
    if user_context:
        base_logger = base_logger.with_context(
            user_id=str(user_context.id), user_email=user_context.email
        )

    ctx = ApiContext(
        request_id=request_id,
        organization=organization_schema,
        user=user_context,
        auth_method=auth_method,
        auth_metadata=auth_metadata,
        logger=base_logger,
    )

    await _check_and_enforce_rate_limit(request, ctx)
    return ctx


async def get_logger(
    context: ApiContext = Depends(get_context),
) -> ContextualLogger:
    """Get a logger with the current authentication context.

    Backward compatibility wrapper that extracts the logger from ApiContext.

    Args:
    ----
        context (AppContext): The unified application context.

    Returns:
    -------
        ContextualLogger: Pre-configured logger with full context.
    """
    return context.logger


async def get_guard_rail_service(
    ctx: ApiContext = Depends(get_context),
) -> GuardRailService:
    """Get a GuardRailService instance for the current organization.

    This dependency creates a GuardRailService instance that can be used to check
    if actions are allowed based on the organization's usage limits and payment status.

    Args:
    ----
        ctx (ApiContext): The authentication context containing organization_id.
        contextual_logger (ContextualLogger): Logger with authentication context.

    Returns:
    -------
        GuardRailService: An instance configured for the current organization.
    """
    contextual_logger = ctx.logger
    return GuardRailService(
        organization_id=ctx.organization.id,
        logger=contextual_logger.with_context(component="guardrail"),
    )


async def get_user(
    db: AsyncSession = Depends(get_db),
    auth0_user: Optional[Auth0User] = Depends(auth0.get_user),
) -> schemas.User:
    """Retrieve user from super user from database.

    Legacy dependency for endpoints that expect User.
    Will fail for API key authentication since API keys don't have user context.

    Args:
    ----
        db (AsyncSession): Database session.
        x_api_key (Optional[str]): API key provided in the request header.
        x_organization_id (Optional[str]): Organization ID provided in the X-Organization-ID header.
        auth0_user (Optional[Auth0User]): User details from Auth0.

    Returns:
    -------
        schemas.User: User details from the database with organizations.

    Raises:
    ------
        HTTPException: If the user is not found in the database or if
            no authentication method is provided.

    """
    # Get auth context and extract user
    if not settings.AUTH_ENABLED:
        user, _, _ = await _authenticate_system_user(db)
    # Auth0 auth
    else:
        if not auth0_user:
            raise HTTPException(status_code=401, detail="User email not found in Auth0")
        user, _, _ = await _authenticate_auth0_user(db, auth0_user)

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


# Add this function to authenticate users with a token directly
async def get_user_from_token(token: str, db: AsyncSession) -> Optional[schemas.User]:
    """Verify the token and return the corresponding user.

    Args:
        token: The authentication token.
        db: The database session.

    Returns:
        The user with organizations if authentication succeeds, None otherwise.
    """
    try:
        # Remove 'Bearer ' prefix if present
        if token.startswith("Bearer "):
            token = token[7:]

        # If auth is disabled, just use the first superuser
        if not settings.AUTH_ENABLED:
            user = await crud.user.get_by_email(db, email=settings.FIRST_SUPERUSER)
            if user:
                return schemas.User.model_validate(user)
            return None

        # Get user ID from the token using the auth module
        from airweave.api.auth import get_user_from_token as auth_get_user

        auth0_user = await auth_get_user(token)
        if not auth0_user:
            return None

        # Get the internal user representation with organizations
        user = await crud.user.get_by_email(db=db, email=auth0_user.email)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        return schemas.User.model_validate(user)
    except Exception as e:
        logger.error(f"Error in get_user_from_token: {e}")
        return None
