"""FastAPI dependencies — thin DI wiring only.

All authentication, caching, authorization, rate-limiting, and analytics
logic lives in ``context_resolver.py``. This module just wires FastAPI
``Depends()`` to the resolver.
"""

from typing import Optional

from fastapi import Depends, Header, HTTPException, Request
from fastapi_auth0 import Auth0User
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
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
