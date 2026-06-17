"""FastAPI dependencies — thin DI wiring only.

All authentication, caching, authorization, rate-limiting, and analytics
logic lives in ``context_resolver.py``. This module just wires FastAPI
``Depends()`` to the resolver.
"""

from datetime import timezone
from typing import Any, Callable, Optional

from fastapi import Depends, Header, HTTPException, Request
from fastapi_auth0 import Auth0User
from jose import jwt as jose_jwt
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.auth import auth0
from airweave.api.context import ApiContext  # noqa: F401 — re-exported for backward compat
from airweave.api.context_resolver import ContextResolver
from airweave.api.inject import Inject  # noqa: F401 — re-exported for backward compat
from airweave.core import container as container_mod
from airweave.core.config import settings
from airweave.core.container import Container
from airweave.core.logging import ContextualLogger
from airweave.core.protocols.cache import ContextCache
from airweave.core.protocols.rate_limiter import RateLimiter
from airweave.core.shared_models import AuthMethod
from airweave.db.session import get_db
from airweave.domains.organizations.repository import ApiKeyRepository, OrganizationRepository
from airweave.domains.sessions.repository import SessionRepository
from airweave.domains.users.repository import UserRepository

_user_repo = UserRepository()
_api_key_repo = ApiKeyRepository()
_org_repo = OrganizationRepository()
_session_repo = SessionRepository()


def get_container() -> Container:
    """Get the DI container. Used by test conftest for dependency_overrides."""
    c = container_mod.container
    if c is None:
        raise RuntimeError("Container not initialized. Call initialize_container() first.")
    return c


def require_org_role(
    check: Callable[[str], bool],
    *,
    block_api_key_auth: bool = False,
) -> Any:
    """Dependency factory enforcing organization-level role checks.

    Args:
        check: Pure predicate (e.g. ``logic.can_manage_api_keys``) that
            receives the user's org role string and returns True if allowed.
        block_api_key_auth: When True, reject API-key-authenticated requests
            immediately (prevents privilege escalation for self-referential
            resources like API keys managing API keys).
    """

    async def _enforce(ctx: ApiContext = Depends(get_context)) -> ApiContext:
        # Checked before system bypass — these auth methods are mutually
        # exclusive (API_KEY vs SYSTEM/INTERNAL_SYSTEM), so ordering is
        # safe.  Keeping this first gives a precise error message.
        if block_api_key_auth and ctx.is_api_key_auth:
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
        session_repo=_session_repo,
    )
    return await resolver.resolve(request, db, auth0_user, x_api_key, x_organization_id)


async def get_logger(
    context: ApiContext = Depends(get_context),
) -> ContextualLogger:
    """Backward-compat wrapper — extracts logger from ApiContext."""
    return context.logger


async def get_user(
    request: Request,
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
        session_repo=_session_repo,
    )
    return await resolver.authenticate_user_only(db, auth0_user, request)


async def _is_token_revoked(token: str, user: schemas.User, db: AsyncSession) -> bool:
    """Check user-wide and per-session revocation for a raw JWT."""
    try:
        claims = jose_jwt.get_unverified_claims(token)
    except Exception:
        return True

    if user.tokens_revoked_at is not None:
        iat = claims.get("iat")
        revoked_ts = user.tokens_revoked_at.replace(tzinfo=timezone.utc).timestamp()
        if iat is None or iat < revoked_ts:
            return True

    sid = claims.get(settings.AUTH0_SID_CLAIM_KEY)
    if sid:
        session = await _session_repo.get_by_session_id(db, sid)
        if session is not None and session.is_revoked:
            return True

    return False


async def get_user_from_token(token: str, db: AsyncSession) -> Optional[schemas.User]:
    """Verify a token and return the corresponding user.

    Used by WebSocket/SSE endpoints that receive tokens directly.
    Checks both user-wide token revocation (``tokens_revoked_at``)
    and per-session revocation via the ``user_session`` table.
    """
    try:
        if token.startswith("Bearer "):
            token = token[7:]

        if not settings.AUTH_ENABLED:
            user = await _user_repo.get_by_email(db, email=settings.FIRST_SUPERUSER)
            if user:
                return schemas.User.model_validate(user)
            return None

        from airweave.api.auth import get_user_from_token as auth_get_user

        auth0_user = await auth_get_user(token)
        if not auth0_user:
            return None

        user = await _user_repo.get_by_email(db=db, email=auth0_user.email)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        user_schema = schemas.User.model_validate(user)
        if await _is_token_revoked(token, user_schema, db):
            return None

        return user_schema
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
