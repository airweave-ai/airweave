"""Dependencies that are used in the API endpoints."""

import uuid
from typing import Optional, Tuple, get_type_hints

from fastapi import Depends, Header, HTTPException, Request
from fastapi_auth0 import Auth0User
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.analytics.contextual_service import (
    AnalyticsContext,
    ContextualAnalyticsService,
    RequestHeaders,
)
from airweave.analytics.service import analytics
from airweave.api.auth import auth0
from airweave.api.context import ApiContext
from airweave.core import container as container_mod
from airweave.core.config import settings
from airweave.core.container import Container
from airweave.core.context_cache_service import context_cache
from airweave.core.exceptions import NotFoundException, RateLimitExceededException
from airweave.core.guard_rail_service import GuardRailService
from airweave.core.logging import ContextualLogger, logger
from airweave.core.rate_limiter_service import RateLimiter
from airweave.core.shared_models import AuthMethod
from airweave.db.session import get_db
from airweave.schemas.rate_limit import RateLimitResult


async def _authenticate_system_user(
    db: AsyncSession,
) -> Tuple[Optional[schemas.User], AuthMethod, dict]:
    """Authenticate system user when auth is disabled."""
    user = await crud.user.get_by_email(db, email=settings.FIRST_SUPERUSER)
    if user:
        user_context = schemas.User.model_validate(user)
        return user_context, AuthMethod.SYSTEM, {"disabled_auth": True}
    return None, AuthMethod.SYSTEM, {}


async def _authenticate_auth0_user(
    db: AsyncSession, auth0_user: Auth0User
) -> Tuple[Optional[schemas.User], AuthMethod, dict]:
    """Authenticate Auth0 user."""
    from datetime import datetime

    try:
        user = await crud.user.get_by_email(db, email=auth0_user.email)
    except NotFoundException:
        logger.error(f"User {auth0_user.email} not found in database")
        return None, AuthMethod.AUTH0, {}

    # Update last active timestamp directly (can't use CRUD during auth flow)

    user_update = schemas.UserUpdate(last_active_at=datetime.utcnow())
    user = await crud.user.update_user_no_auth(db, id=user.id, obj_in=user_update)

    user_context = schemas.User.model_validate(user)
    return user_context, AuthMethod.AUTH0, {"auth0_id": auth0_user.id}


def _extract_client_ip(request: Request) -> str:
    """Extract client IP from request headers.

    Checks X-Forwarded-For header first (for proxied requests),
    then falls back to direct client IP.

    Args:
    ----
        request (Request): FastAPI request object

    Returns:
    -------
        str: Client IP address or "unknown" if not available

    """
    # Check X-Forwarded-For first (for proxied requests)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can be a comma-separated list, take the first one (original client)
        return forwarded_for.split(",")[0].strip()

    # Fallback to direct client IP
    return request.client.host if request.client else "unknown"


async def _authenticate_api_key(
    db: AsyncSession, api_key: str, request: Request
) -> Tuple[None, AuthMethod, dict, str]:
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
            return None, AuthMethod.API_KEY, auth_metadata, str(org_id)

        # Cache miss - validate API key via CRUD
        api_key_obj = await crud.api_key.get_by_key(db, key=api_key)
        org_id = api_key_obj.organization_id

        # Log API key usage with structured dimensions (flows to Azure LAW)
        client_ip = _extract_client_ip(request)
        audit_logger = logger.with_context(event_type="api_key_usage")
        audit_logger.info(
            f"API key usage: key={api_key_obj.id} org={org_id} ip={client_ip} "
            f"endpoint={request.url.path} created_by={api_key_obj.created_by_email}"
        )

        # Cache the mapping for next time
        await context_cache.set_api_key_org_id(api_key, org_id)

        auth_metadata = {
            "api_key_id": str(api_key_obj.id),
            "created_by": api_key_obj.created_by_email,
        }

        return None, AuthMethod.API_KEY, auth_metadata, str(org_id)

    except (ValueError, NotFoundException) as e:
        logger.error(f"API key validation failed: {e}")
        if "expired" in str(e):
            raise HTTPException(status_code=403, detail="API key has expired") from e
        raise HTTPException(status_code=403, detail="Invalid or expired API key") from e


def _resolve_organization_id(
    x_organization_id: Optional[str],
    user_context: Optional[schemas.User],
    auth_method: AuthMethod,
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
    if auth_method in [AuthMethod.SYSTEM, AuthMethod.AUTH0] and user_context:
        if user_context.primary_organization_id:
            return str(user_context.primary_organization_id)
    elif auth_method == AuthMethod.API_KEY and api_key_org_id:
        return api_key_org_id

    raise HTTPException(
        status_code=400,
        detail="Organization context required (X-Organization-ID header missing)",
    )


async def _validate_organization_access(
    db: AsyncSession,
    organization_id: str,
    user_context: Optional[schemas.User],
    auth_method: AuthMethod,
    x_api_key: Optional[str],
) -> None:
    """Validate that the user/API key has access to the requested organization."""
    # For user-based auth, verify the user has access to the requested organization
    if user_context and auth_method in [AuthMethod.AUTH0, AuthMethod.SYSTEM]:
        user_org_ids = [str(org.organization.id) for org in user_context.user_organizations]
        if organization_id not in user_org_ids:
            raise HTTPException(
                status_code=403,
                detail=f"User does not have access to organization {organization_id}",
            )

    # For API key auth, verify the API key belongs to the requested organization
    elif auth_method == AuthMethod.API_KEY and x_api_key:
        api_key_obj = await crud.api_key.get_by_key(db, key=x_api_key)
        if str(api_key_obj.organization_id) != organization_id:
            raise HTTPException(
                status_code=403,
                detail=f"API key does not have access to organization {organization_id}",
            )


async def _get_or_fetch_user_context(
    db: AsyncSession,
    auth0_user: Auth0User,
) -> Tuple[Optional[schemas.User], AuthMethod, dict]:
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
        auth_method = AuthMethod.AUTH0
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

    Rate limiting only applies to API key authentication. Auth0 (access token)
    and system authentication are excluded from rate limiting.

    Stores RateLimitResult in request.state for middleware to add headers.

    Args:
    ----
        request (Request): The FastAPI request object to store rate limit info.
        ctx (ApiContext): API context containing organization and logger.

    Raises:
    ------
        RateLimitExceededException: If rate limit is exceeded.
    """
    # Only apply rate limiting to API key authentication
    # Auth0 (access token) and system auth are excluded
    if ctx.auth_method in [AuthMethod.AUTH0, AuthMethod.SYSTEM]:
        ctx.logger.debug(f"Skipping rate limit for auth method: {ctx.auth_method.value}")
        request.state.rate_limit_result = RateLimitResult(
            allowed=True,
            retry_after=0.0,
            limit=9999,  # 9999 indicates unlimited/not applicable
            remaining=9999,  # Not applicable for excluded auth methods
        )
        return

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
    auth_method: Optional[AuthMethod] = None
    auth_metadata = {}
    api_key_org_id = None  # For API key auth, this is already resolved

    # Determine authentication method and context
    if not settings.AUTH_ENABLED:
        user_context, auth_method, auth_metadata = await _authenticate_system_user(db)
    elif auth0_user:
        user_context, auth_method, auth_metadata = await _get_or_fetch_user_context(db, auth0_user)
    elif x_api_key:
        user_context, auth_method, auth_metadata, api_key_org_id = await _authenticate_api_key(
            db, x_api_key, request
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
        auth_method=auth_method.value,
        context_base="api",
    )

    # Add user context if available
    if user_context:
        base_logger = base_logger.with_context(
            user_id=str(user_context.id), user_email=user_context.email
        )

    # Create analytics context with only the fields we need
    analytics_context = AnalyticsContext(
        auth_method=auth_method.value,
        organization_id=str(organization_schema.id),
        organization_name=organization_schema.name,
        request_id=request_id,
        user_id=str(user_context.id) if user_context else None,
    )

    # Create analytics service with context and headers
    headers = _extract_headers_from_request(request)
    analytics_service = ContextualAnalyticsService(
        base_service=analytics,
        context=analytics_context,
        headers=headers,
    )

    # Create the context
    ctx = ApiContext(
        request_id=request_id,
        organization=organization_schema,
        user=user_context,
        auth_method=auth_method,
        auth_metadata=auth_metadata,
        analytics=analytics_service,
        logger=base_logger,
    )

    if user_context:
        analytics_service.identify_user()

    # Store context in request state for middleware access
    request.state.api_context = ctx

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


def _extract_headers_from_request(request: Request) -> RequestHeaders:
    """Extract tracking-relevant headers from the request.

    Easily extensible - just add new header mappings here when introducing new headers.
    """
    headers = request.headers

    return RequestHeaders(
        # Standard headers
        user_agent=headers.get("user-agent"),
        # Client/Frontend headers
        client_name=headers.get("x-client-name"),
        client_version=headers.get("x-client-version"),
        session_id=headers.get("x-airweave-session-id"),
        # SDK headers
        sdk_name=headers.get("x-sdk-name") or headers.get("x-fern-sdk-name"),
        sdk_version=headers.get("x-sdk-version") or headers.get("x-fern-sdk-version"),
        # Fern-specific headers
        fern_language=headers.get("x-fern-language"),
        fern_runtime=headers.get("x-fern-runtime"),
        fern_runtime_version=headers.get("x-fern-runtime-version"),
        # Agent framework headers
        framework_name=headers.get("x-framework-name"),
        framework_version=headers.get("x-framework-version"),
        # Request tracking - use the request_id from middleware, not headers
        request_id=getattr(request.state, "request_id", "unknown"),
    )


# ---------------------------------------------------------------------------
# DI Container
# ---------------------------------------------------------------------------


def get_container() -> Container:
    """Get the DI container. Initialized at startup."""
    c = container_mod.container
    if c is None:
        raise RuntimeError("Container not initialized. Call initialize_container() first.")
    return c


# ---------------------------------------------------------------------------
# Protocol Injection
# ---------------------------------------------------------------------------

# Cache of protocol_type → Container field name, built once at first call.
_INJECT_CACHE: dict[type, str] = {}


def _resolve_field_name(protocol_type: type) -> str:
    """Find which Container field matches the given protocol type.

    Uses get_type_hints() to introspect the Container dataclass.
    Result is cached so the lookup happens at most once per protocol type.
    """
    if not _INJECT_CACHE:
        # Populate cache on first call
        for name, hint in get_type_hints(Container).items():
            _INJECT_CACHE[hint] = name

    field_name = _INJECT_CACHE.get(protocol_type)
    if field_name is None:
        available = list(_INJECT_CACHE.values())
        raise TypeError(
            f"No binding for {protocol_type.__name__} in Container. Available fields: {available}"
        )
    return field_name


def Inject(protocol_type: type):  # noqa: N802 — uppercase to match FastAPI convention
    """Resolve a protocol implementation from the DI container.

    Works like ``Depends()`` but looks up the implementation by protocol type
    instead of requiring the caller to know about the Container internals.

    Usage in FastAPI endpoints::

        from airweave.api.deps import Inject
        from airweave.core.protocols import EventBus, WebhookAdmin


        @router.post("/")
        async def create(
            event_bus: EventBus = Inject(EventBus),
            webhook_admin: WebhookAdmin = Inject(WebhookAdmin),
        ):
            await event_bus.publish(...)
    """
    field_name = _resolve_field_name(protocol_type)

    def _resolve(c: Container = Depends(get_container)):
        return getattr(c, field_name)

    return Depends(_resolve)
