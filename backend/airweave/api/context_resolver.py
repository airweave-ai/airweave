"""Context resolution for API requests.

Handles authentication, caching, authorization, rate limiting, and analytics
setup. Extracted from deps.py so that file stays thin DI wiring only.

All data access goes through injected protocols — no direct crud imports.
Testable by passing fakes for every dependency.
"""

import uuid
from dataclasses import dataclass, field
from typing import Optional

from fastapi import HTTPException, Request
from fastapi_auth0 import Auth0User
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.analytics.service import analytics
from airweave.api.context import ApiContext, RequestHeaders
from airweave.core.config import settings
from airweave.core.exceptions import NotFoundException, RateLimitExceededException
from airweave.core.logging import logger
from airweave.core.protocols.cache import ContextCache
from airweave.core.protocols.rate_limiter import RateLimiter
from airweave.core.shared_models import AuthMethod
from airweave.domains.organizations.protocols import (
    ApiKeyRepositoryProtocol,
    OrganizationRepositoryProtocol,
)
from airweave.domains.users.protocols import UserRepositoryProtocol
from airweave.schemas.rate_limit import RateLimitResult

# ---------------------------------------------------------------------------
# Auth result
# ---------------------------------------------------------------------------


@dataclass
class AuthResult:
    """Result of authentication — replaces the old tuple returns."""

    user: Optional[schemas.User] = None
    method: AuthMethod = AuthMethod.SYSTEM
    metadata: dict = field(default_factory=dict)
    api_key_org_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


class ContextResolver:
    """Resolves a full ApiContext from raw request inputs.

    Handles the auth → cache → org-lookup → access-check → analytics → rate-limit
    pipeline. Constructed per-request with injected dependencies.
    """

    def __init__(
        self,
        *,
        cache: ContextCache,
        rate_limiter: RateLimiter,
        user_repo: UserRepositoryProtocol,
        api_key_repo: ApiKeyRepositoryProtocol,
        org_repo: OrganizationRepositoryProtocol,
    ) -> None:
        """Initialize ContextResolver."""
        self._cache = cache
        self._rate_limiter = rate_limiter
        self._users = user_repo
        self._api_keys = api_key_repo
        self._orgs = org_repo

    async def resolve(
        self,
        request: Request,
        db: AsyncSession,
        auth0_user: Optional[Auth0User],
        x_api_key: Optional[str],
        x_organization_id: Optional[str],
    ) -> ApiContext:
        """Build a fully populated ApiContext for this request."""
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

        auth = await self._authenticate(db, auth0_user, x_api_key, request)

        organization_id = self._resolve_organization_id(x_organization_id, auth)
        organization = await self._get_or_fetch_organization(db, organization_id)

        await self._validate_organization_access(db, organization_id, auth, x_api_key)

        ctx = self._build_context(request, request_id, auth, organization)

        request.state.api_context = ctx
        await self._check_and_enforce_rate_limit(request, ctx)
        return ctx

    async def authenticate_user_only(
        self, db: AsyncSession, auth0_user: Optional[Auth0User]
    ) -> schemas.User:
        """Lightweight auth for endpoints that only need a User (no org context).

        Used by ``deps.get_user``.
        """
        if not settings.AUTH_ENABLED:
            user = await self._fetch_system_user(db)
            if user:
                return user
            raise HTTPException(status_code=401, detail="User not found")

        if not auth0_user:
            raise HTTPException(status_code=401, detail="User email not found in Auth0")

        user = await self._fetch_auth0_user(db, auth0_user)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def _authenticate(
        self,
        db: AsyncSession,
        auth0_user: Optional[Auth0User],
        x_api_key: Optional[str],
        request: Request,
    ) -> AuthResult:
        if not settings.AUTH_ENABLED:
            return await self._authenticate_system(db)
        if auth0_user:
            return await self._authenticate_auth0(db, auth0_user)
        if x_api_key:
            return await self._authenticate_api_key(db, x_api_key, request)
        raise HTTPException(status_code=401, detail="No valid authentication provided")

    async def _authenticate_system(self, db: AsyncSession) -> AuthResult:
        user = await self._fetch_system_user(db)
        return AuthResult(
            user=user,
            method=AuthMethod.SYSTEM,
            metadata={"disabled_auth": True},
        )

    async def _authenticate_auth0(self, db: AsyncSession, auth0_user: Auth0User) -> AuthResult:
        user = None
        if auth0_user.email:
            user = await self._cache.get_user(auth0_user.email)
        if not user:
            user = await self._fetch_auth0_user(db, auth0_user)
            if user:
                await self._cache.set_user(user)

        return AuthResult(
            user=user,
            method=AuthMethod.AUTH0,
            metadata={"auth0_id": auth0_user.id},
        )

    async def _authenticate_api_key(
        self, db: AsyncSession, api_key: str, request: Request
    ) -> AuthResult:
        try:
            org_id = await self._cache.get_api_key_org_id(api_key)
            if org_id:
                return AuthResult(
                    method=AuthMethod.API_KEY,
                    metadata={"api_key_id": "cached", "created_by": None},
                    api_key_org_id=str(org_id),
                )

            api_key_obj = await self._api_keys.get_by_key(db, key=api_key)
            org_id = api_key_obj.organization_id

            client_ip = _extract_client_ip(request)
            audit_logger = logger.with_context(event_type="api_key_usage")
            audit_logger.info(
                f"API key usage: key={api_key_obj.id} org={org_id} ip={client_ip} "
                f"endpoint={request.url.path} created_by={api_key_obj.created_by_email}"
            )

            await self._cache.set_api_key_org_id(api_key, org_id)

            return AuthResult(
                method=AuthMethod.API_KEY,
                metadata={
                    "api_key_id": str(api_key_obj.id),
                    "created_by": api_key_obj.created_by_email,
                },
                api_key_org_id=str(org_id),
            )

        except (ValueError, NotFoundException) as e:
            logger.error(f"API key validation failed: {e}")
            if "expired" in str(e):
                raise HTTPException(status_code=403, detail="API key has expired") from e
            raise HTTPException(status_code=403, detail="Invalid or expired API key") from e

    # ------------------------------------------------------------------
    # User fetching (DB)
    # ------------------------------------------------------------------

    async def _fetch_system_user(self, db: AsyncSession) -> Optional[schemas.User]:
        user = await self._users.get_by_email(db, email=settings.FIRST_SUPERUSER)
        if user:
            return schemas.User.model_validate(user)
        return None

    async def _fetch_auth0_user(
        self, db: AsyncSession, auth0_user: Auth0User
    ) -> Optional[schemas.User]:
        from datetime import datetime

        if not auth0_user.email:
            return None
        try:
            user = await self._users.get_by_email(db, email=auth0_user.email)
        except NotFoundException:
            logger.error(f"User {auth0_user.email} not found in database")
            return None

        user_update = schemas.UserUpdate(last_active_at=datetime.utcnow())
        user = await self._users.update_user_no_auth(db, id=user.id, obj_in=user_update)
        return schemas.User.model_validate(user)

    # ------------------------------------------------------------------
    # Organization resolution
    # ------------------------------------------------------------------

    def _resolve_organization_id(
        self,
        x_organization_id: Optional[str],
        auth: AuthResult,
    ) -> str:
        if x_organization_id:
            return x_organization_id

        if auth.method in (AuthMethod.SYSTEM, AuthMethod.AUTH0) and auth.user:
            if auth.user.primary_organization_id:
                return str(auth.user.primary_organization_id)

        if auth.method == AuthMethod.API_KEY and auth.api_key_org_id:
            return auth.api_key_org_id

        raise HTTPException(
            status_code=400,
            detail="Organization context required (X-Organization-ID header missing)",
        )

    async def _get_or_fetch_organization(
        self, db: AsyncSession, organization_id: str
    ) -> schemas.Organization:
        org = await self._cache.get_organization(uuid.UUID(organization_id))
        if not org:
            org = await self._orgs.get(
                db, id=uuid.UUID(organization_id), skip_access_validation=True, enrich=True
            )
            if not org:
                raise HTTPException(
                    status_code=404, detail=f"Organization {organization_id} not found"
                )
            await self._cache.set_organization(org)
        return org

    # ------------------------------------------------------------------
    # Access validation
    # ------------------------------------------------------------------

    async def _validate_organization_access(
        self,
        db: AsyncSession,
        organization_id: str,
        auth: AuthResult,
        x_api_key: Optional[str],
    ) -> None:
        if auth.user and auth.method in (AuthMethod.AUTH0, AuthMethod.SYSTEM):
            user_org_ids = [str(org.organization.id) for org in auth.user.user_organizations]
            if organization_id not in user_org_ids:
                raise HTTPException(
                    status_code=403,
                    detail=f"User does not have access to organization {organization_id}",
                )

        elif auth.method == AuthMethod.API_KEY and x_api_key:
            api_key_obj = await self._api_keys.get_by_key(db, key=x_api_key)
            if str(api_key_obj.organization_id) != organization_id:
                raise HTTPException(
                    status_code=403,
                    detail=f"API key does not have access to organization {organization_id}",
                )

    # ------------------------------------------------------------------
    # Context building
    # ------------------------------------------------------------------

    def _build_context(
        self,
        request: Request,
        request_id: str,
        auth: AuthResult,
        organization: schemas.Organization,
    ) -> ApiContext:
        base_logger = logger.with_context(
            request_id=request_id,
            organization_id=str(organization.id),
            organization_name=organization.name,
            auth_method=auth.method.value,
            context_base="api",
        )
        if auth.user:
            base_logger = base_logger.with_context(
                user_id=str(auth.user.id), user_email=auth.user.email
            )

        headers = _extract_headers(request)

        ctx = ApiContext(
            request_id=request_id,
            organization=organization,
            user=auth.user,
            auth_method=auth.method,
            auth_metadata=auth.metadata,
            headers=headers,
            logger=base_logger,
        )

        if auth.user:
            analytics.identify_user(
                str(auth.user.id),
                {
                    "auth_method": auth.method.value,
                    "organization_name": organization.name,
                    "client_name": headers.client_name,
                    "sdk_name": headers.sdk_name,
                    "session_id": headers.session_id,
                },
            )

        return ctx

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    async def _check_and_enforce_rate_limit(self, request: Request, ctx: ApiContext) -> None:
        if ctx.auth_method in (AuthMethod.AUTH0, AuthMethod.SYSTEM):
            request.state.rate_limit_result = RateLimitResult(
                allowed=True,
                retry_after=0.0,
                limit=9999,
                remaining=9999,
            )
            return

        try:
            result = await self._rate_limiter.check(ctx.organization)
            request.state.rate_limit_result = result
        except RateLimitExceededException:
            raise
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}. Allowing request.")
            request.state.rate_limit_result = RateLimitResult(
                allowed=True,
                retry_after=0.0,
                limit=0,
                remaining=9999,
            )


# ------------------------------------------------------------------
# Module-level helpers (pure functions, no state)
# ------------------------------------------------------------------


def _extract_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _extract_headers(request: Request) -> RequestHeaders:
    h = request.headers
    return RequestHeaders(
        user_agent=h.get("user-agent"),
        client_name=h.get("x-client-name"),
        client_version=h.get("x-client-version"),
        session_id=h.get("x-airweave-session-id"),
        sdk_name=h.get("x-sdk-name") or h.get("x-fern-sdk-name"),
        sdk_version=h.get("x-sdk-version") or h.get("x-fern-sdk-version"),
        fern_language=h.get("x-fern-language"),
        fern_runtime=h.get("x-fern-runtime"),
        fern_runtime_version=h.get("x-fern-runtime-version"),
        framework_name=h.get("x-framework-name"),
        framework_version=h.get("x-framework-version"),
        request_id=getattr(request.state, "request_id", "unknown"),
    )
