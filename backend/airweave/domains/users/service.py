"""User service — create-or-update with Auth0 integration.

A single ``UserServiceProtocol`` on the DI container, consumed by the
``users.py`` endpoint.  Delegates provisioning to ``OrganizationServiceProtocol``
and org-membership queries to ``UserOrganizationRepositoryProtocol``.
"""

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.analytics import business_events
from airweave.api.context import ApiContext
from airweave.core.logging import logger
from airweave.core.protocols.email import EmailService
from airweave.core.shared_models import AuthMethod
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.organizations.protocols import (
    OrganizationServiceProtocol,
    UserOrganizationRepositoryProtocol,
)
from airweave.domains.users.protocols import UserRepositoryProtocol, UserServiceProtocol
from airweave.domains.users.types import CreateOrUpdateResult


class UserService(UserServiceProtocol):
    """Implements ``UserServiceProtocol``."""

    def __init__(
        self,
        *,
        user_repo: UserRepositoryProtocol,
        org_service: OrganizationServiceProtocol,
        user_org_repo: UserOrganizationRepositoryProtocol,
        email_service: EmailService,
    ) -> None:
        """Initialize UserService."""
        self._user_repo = user_repo
        self._org_service = org_service
        self._user_org_repo = user_org_repo
        self._email = email_service

    # ------------------------------------------------------------------
    # Create or update
    # ------------------------------------------------------------------

    async def create_or_update(
        self,
        db: AsyncSession,
        user_data: schemas.UserCreate,
        auth0_user: Any,
    ) -> CreateOrUpdateResult:
        """Create or update a user with Auth0 organization sync.

        Email is the source of truth — if the auth0_id changed (e.g.
        account linking), it gets updated silently.  Handles welcome
        email and analytics for new users.
        """
        from airweave.core.exceptions import NotFoundException

        existing_user = None
        try:
            existing_user = await self._user_repo.get_by_email(db, email=user_data.email)
        except NotFoundException:
            logger.info(f"User {user_data.email} not found, creating...")

        if existing_user:
            return await self._handle_existing_user(db, existing_user, user_data, auth0_user)

        return await self._provision_new_user(db, user_data, auth0_user)

    # ------------------------------------------------------------------
    # Organization queries
    # ------------------------------------------------------------------

    async def get_user_organizations(
        self,
        db: AsyncSession,
        user_id: UUID,
    ) -> list[schemas.OrganizationWithRole]:
        """Return all organizations the user belongs to, with roles."""
        return await self._user_org_repo.get_user_memberships_with_orgs(db, user_id=user_id)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _handle_existing_user(
        self,
        db: AsyncSession,
        existing_user: Any,
        user_data: schemas.UserCreate,
        auth0_user: Any,
    ) -> CreateOrUpdateResult:
        """Handle existing user: update auth0_id if changed, then sync orgs.

        Email is the source of truth for identity.  Auth0 account linking
        guarantees a stable ``sub``, so we simply store whatever Auth0 sends.
        """
        incoming_auth0_id = auth0_user.id if auth0_user else user_data.auth0_id

        if incoming_auth0_id and existing_user.auth0_id != incoming_auth0_id:
            logger.info(
                f"Updating auth0_id for user {user_data.email}: "
                f"{existing_user.auth0_id} → {incoming_auth0_id}"
            )
            existing_user = await self._user_repo.update_user_no_auth(
                db,
                id=existing_user.id,
                obj_in=schemas.UserUpdate(auth0_id=incoming_auth0_id),
            )

        try:
            updated_user = await self._org_service.sync_user_organizations(db, existing_user)
            logger.info(f"Synced Auth0 organizations for existing user: {user_data.email}")
            return CreateOrUpdateResult(
                user=schemas.User.model_validate(updated_user), is_new=False
            )
        except Exception as e:
            logger.warning(f"Failed to sync Auth0 organizations for user {user_data.email}: {e}")
            return CreateOrUpdateResult(
                user=schemas.User.model_validate(existing_user), is_new=False
            )

    async def _provision_new_user(
        self,
        db: AsyncSession,
        user_data: schemas.UserCreate,
        auth0_user: Any,
    ) -> CreateOrUpdateResult:
        """Provision a new user via org service, with CRUD fallback."""
        try:
            user_dict = user_data.model_dump()
            if auth0_user:
                user_dict["auth0_id"] = auth0_user.id

            user = await self._org_service.provision_new_user(db, user_dict, create_org=False)
            logger.info(f"Created new user {user.email}.")

            self._track_analytics(user)
            await self._send_welcome(user)

            return CreateOrUpdateResult(user=schemas.User.model_validate(user), is_new=True)

        except Exception as e:
            logger.error(f"Failed to create user with Auth0 integration: {e}")
            result = await self._fallback_create(db, user_data)
            await self._send_welcome_from_schema(result.user)
            return result

    def _track_analytics(self, user: Any) -> None:
        """Best-effort analytics tracking for new user creation."""
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

    async def _send_welcome(self, user: Any) -> None:
        """Best-effort welcome email for a new user (ORM model)."""
        try:
            await self._email.send_welcome(user.email, user.full_name or user.email)
        except Exception as e:
            logger.warning(f"Failed to send welcome email to {user.email}: {e}")

    async def _send_welcome_from_schema(self, user: schemas.User) -> None:
        """Best-effort welcome email for a new user (Pydantic schema)."""
        try:
            await self._email.send_welcome(user.email, user.full_name or user.email)
        except Exception as e:
            logger.warning(f"Failed to send welcome email to {user.email}: {e}")

    async def _fallback_create(
        self,
        db: AsyncSession,
        user_data: schemas.UserCreate,
    ) -> CreateOrUpdateResult:
        """Fallback: create user + org via CRUD when Auth0 integration fails."""
        async with UnitOfWork(db) as uow:
            user, organization = await crud.user.create_with_organization(
                db, obj_in=user_data, uow=uow
            )
            _ = await crud.api_key.create(
                db,
                obj_in=schemas.APIKeyCreate(),
                ctx=ApiContext(
                    request_id=str(uuid4()),
                    user=user,
                    organization=organization,
                    auth_method=AuthMethod.AUTH0,
                ),
                uow=uow,
            )
        logger.info(f"Created user {user.email} with fallback method")
        return CreateOrUpdateResult(user=user, is_new=True)
