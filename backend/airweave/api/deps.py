"""FastAPI dependencies — thin DI wiring only.

All authentication, caching, authorization, rate-limiting, and analytics
logic lives in ``context_resolver.py``. This module just wires FastAPI
``Depends()`` to the resolver.
"""

import time
from typing import Any, Callable, Optional

from fastapi import Depends, Header, HTTPException, Request
from fastapi_auth0 import Auth0User
from jose import jwt as jose_jwt
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.auth import auth0
from airweave.api.context import ApiContext  # noqa: F401 — re-exported for backward compat
from airweave.api.context_resolver import ContextResolver
from airweave.api.inject import Inject  # noqa: F401 — re-exported for backward compat
from airweave.core import container as container_mod
from airweave.core.config import settings
from airweave.core.container import Container
from airweave.core.exceptions import ReauthenticationRequiredException
from airweave.core.logging import ContextualLogger, logger
from airweave.core.protocols.cache import ContextCache
from airweave.core.protocols.rate_limiter import RateLimiter
from airweave.core.shared_models import AuthMethod
from airweave.db.session import get_db
from airweave.domains.organizations.repository import ApiKeyRepository, OrganizationRepository
from airweave.domains.users.repository import UserRepository

_user_repo = UserRepository()
_api_key_repo = ApiKeyRepository()
_org_repo = OrganizationRepository()


def get_container() -> Container:
    """Get the DI container. Used by test conftest for dependency_overrides."""
    c = container_mod.container
    if c is None:
        raise RuntimeError("Container not initialized. Call initialize_container() first.")
    return c


# ---------------------------------------------------------------------------
# Re-authentication recency checks (CASA-29)
# ---------------------------------------------------------------------------
# TODO(CASA-29): Once PR #1746 merges, replace _extract_claims() with
# ``from airweave.api.jwt_utils import extract_claims``.


def _extract_claims(request: Request) -> Optional[dict]:
    """Extract unverified JWT claims from the Bearer token, or None.

    Safe to use after ``fastapi_auth0`` has already verified the token
    signature — this avoids threading claims through the entire auth
    pipeline.
    """
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    try:
        return jose_jwt.get_unverified_claims(auth_header[7:])
    except Exception:
        logger.debug("Failed to extract unverified JWT claims from request")
        return None


def _extract_auth_time(request: Request) -> Optional[int]:
    """Extract the auth_time claim from the JWT in the request.

    Returns None if the claim is absent, non-numeric, or not a
    plausible epoch timestamp (rejects negative values and timestamps
    more than 60 s in the future to guard against clock skew or
    malicious claims).
    """
    claims = _extract_claims(request)
    if claims is None:
        return None
    value = claims.get(settings.AUTH0_AUTH_TIME_CLAIM_KEY)
    if isinstance(value, (int, float)):
        ts = int(value)
        now = int(time.time())
        if 0 < ts <= now + 60:
            return ts
    return None


_REAUTH_SKIP_METHODS = frozenset(
    {
        AuthMethod.SYSTEM,
        AuthMethod.INTERNAL_SYSTEM,
        AuthMethod.STRIPE_WEBHOOK,
        AuthMethod.OAUTH_CALLBACK,
    }
)


def _check_auth_recency(
    auth_time: Optional[int],
    max_age_seconds: int,
    auth_method: AuthMethod,
) -> None:
    """Raise ReauthenticationRequiredException if auth is stale.

    Pure check — no logging.  Callers are responsible for emitting
    audit entries with full request context (user, org, request_id).

    Skips for non-interactive auth methods and when max_age_seconds
    is 0 (disabled).  Fails closed when auth_time is None.
    """
    if max_age_seconds == 0:
        return

    if auth_method in _REAUTH_SKIP_METHODS:
        return

    if auth_time is None:
        raise ReauthenticationRequiredException(max_age=max_age_seconds)

    age = int(time.time()) - auth_time
    if age > max_age_seconds:
        raise ReauthenticationRequiredException(max_age=max_age_seconds)


# ---------------------------------------------------------------------------
# Authorization dependencies
# ---------------------------------------------------------------------------


def require_org_role(
    check: Callable[[str], bool],
    *,
    block_api_key_auth: bool = False,
    recent_auth_seconds: Optional[int] = None,
) -> Any:
    """Dependency factory enforcing organization-level role checks.

    Args:
        check: Pure predicate (e.g. ``logic.can_manage_api_keys``) that
            receives the user's org role string and returns True if allowed.
        block_api_key_auth: When True, reject API-key-authenticated requests
            immediately (prevents privilege escalation for self-referential
            resources like API keys managing API keys).
        recent_auth_seconds: When set, require the user's last interactive
            login to be within this many seconds.  Implicitly blocks API
            key auth since API keys cannot re-authenticate interactively.
    """

    async def _enforce(
        request: Request,
        ctx: ApiContext = Depends(get_context),
    ) -> ApiContext:
        # API key auth is blocked when explicitly requested OR when
        # recency is required (API keys cannot re-authenticate).
        if ctx.is_api_key_auth and (block_api_key_auth or recent_auth_seconds is not None):
            raise HTTPException(
                status_code=403,
                detail="API key authentication is not permitted for this operation",
            )

        if ctx.auth_method in (AuthMethod.SYSTEM, AuthMethod.INTERNAL_SYSTEM):
            return ctx

        if ctx.user is None:
            raise HTTPException(
                status_code=403,
                detail="This operation requires user authentication",
            )

        role = ctx.user.organization_roles.get(ctx.organization.id)
        if role is None or not check(role):
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions for this operation",
            )

        if recent_auth_seconds is not None:
            auth_time = _extract_auth_time(request)
            try:
                _check_auth_recency(auth_time, recent_auth_seconds, ctx.auth_method)
            except ReauthenticationRequiredException:
                ctx.logger.with_context(event_type="reauth_challenge").info(
                    f"Re-authentication required: auth_time={auth_time} "
                    f"max_age={recent_auth_seconds}s"
                )
                raise

        return ctx

    return Depends(_enforce)


def require_recent_auth(max_age_seconds: int) -> Any:
    """Dependency factory enforcing authentication recency only.

    Use for endpoints that perform their own role checks inline (e.g.
    organization member management) but still need step-up auth.
    Always blocks API key auth.

    Returns ApiContext — drop-in replacement for ``Depends(get_context)``.
    """

    async def _enforce(
        request: Request,
        ctx: ApiContext = Depends(get_context),
    ) -> ApiContext:
        if ctx.is_api_key_auth:
            raise HTTPException(
                status_code=403,
                detail="API key authentication is not permitted for this operation",
            )
        auth_time = _extract_auth_time(request)
        try:
            _check_auth_recency(auth_time, max_age_seconds, ctx.auth_method)
        except ReauthenticationRequiredException:
            ctx.logger.with_context(event_type="reauth_challenge").info(
                f"Re-authentication required: auth_time={auth_time} max_age={max_age_seconds}s"
            )
            raise
        return ctx

    return Depends(_enforce)


async def get_context(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_organization_id: Optional[str] = Header(None, alias="X-Organization-ID"),
    auth0_user: Optional[Auth0User] = Depends(auth0.get_user),
    cache: ContextCache = Inject(ContextCache),
    rate_limiter: RateLimiter = Inject(RateLimiter),
) -> ApiContext:
    """Create unified API context for the request."""
    resolver = ContextResolver(
        cache=cache,
        rate_limiter=rate_limiter,
        user_repo=_user_repo,
        api_key_repo=_api_key_repo,
        org_repo=_org_repo,
    )
    return await resolver.resolve(request, db, auth0_user, x_api_key, x_organization_id)


async def get_logger(
    context: ApiContext = Depends(get_context),
) -> ContextualLogger:
    """Backward-compat wrapper — extracts logger from ApiContext."""
    return context.logger


async def get_user(
    db: AsyncSession = Depends(get_db),
    auth0_user: Optional[Auth0User] = Depends(auth0.get_user),
    cache: ContextCache = Inject(ContextCache),
    rate_limiter: RateLimiter = Inject(RateLimiter),
) -> schemas.User:
    """Lightweight auth for endpoints that only need a User (no org context)."""
    resolver = ContextResolver(
        cache=cache,
        rate_limiter=rate_limiter,
        user_repo=_user_repo,
        api_key_repo=_api_key_repo,
        org_repo=_org_repo,
    )
    return await resolver.authenticate_user_only(db, auth0_user)


async def get_user_from_token(token: str, db: AsyncSession) -> Optional[schemas.User]:
    """Verify a token and return the corresponding user.

    Used by WebSocket/SSE endpoints that receive tokens directly.
    """
    try:
        if token.startswith("Bearer "):
            token = token[7:]

        if not settings.AUTH_ENABLED:
            user = await crud.user.get_by_email(db, email=settings.FIRST_SUPERUSER)
            if user:
                return schemas.User.model_validate(user)
            return None

        from airweave.api.auth import get_user_from_token as auth_get_user

        auth0_user = await auth_get_user(token)
        if not auth0_user:
            return None

        user = await crud.user.get_by_email(db=db, email=auth0_user.email)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        return schemas.User.model_validate(user)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Connect Session
# ---------------------------------------------------------------------------


def _extract_bearer_token(authorization: str) -> str:
    """Extract token from Bearer authorization header.

    Args:
        authorization: Authorization header value (e.g., "Bearer <token>")

    Returns:
        The extracted token string

    Raises:
        HTTPException: If authorization header doesn't start with "Bearer "
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    return authorization[7:]


async def get_connect_session(
    authorization: str = Header(..., alias="Authorization"),
) -> schemas.ConnectSessionContext:
    """Validate connect session token and return session context.

    This dependency is used for endpoints that authenticate via short-lived
    connect session tokens instead of API keys or Auth0.

    Args:
        authorization: Authorization header containing "Bearer <session_token>"

    Returns:
        ConnectSessionContext with decoded session data

    Raises:
        HTTPException: If token is missing, malformed, invalid, or expired
    """
    import uuid
    from datetime import datetime, timezone

    from airweave.platform.auth.state import verify_state
    from airweave.schemas.connect_session import ConnectSessionContext, ConnectSessionMode

    token = _extract_bearer_token(authorization)

    try:
        payload = verify_state(token, max_age_seconds=10 * 60)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    mode_str = payload.get("mode", "all")
    try:
        mode = ConnectSessionMode(mode_str)
    except ValueError:
        mode = ConnectSessionMode.ALL

    try:
        return ConnectSessionContext(
            session_id=uuid.UUID(payload["sid"]),
            organization_id=uuid.UUID(payload["oid"]),
            collection_id=payload["cid"],
            allowed_integrations=payload.get("int"),
            mode=mode,
            end_user_id=payload.get("uid"),
            expires_at=datetime.fromtimestamp(payload["ts"] + 600, tz=timezone.utc),
        )
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=401, detail="Invalid session token payload") from e
