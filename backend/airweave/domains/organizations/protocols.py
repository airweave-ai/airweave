"""Protocols for the organization domain."""

from datetime import datetime
from typing import Any, Optional, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.api_key import APIKey
from airweave.models.organization import Organization
from airweave.models.user import User
from airweave.models.user_organization import UserOrganization

# ---------------------------------------------------------------------------
# Repository protocols
# ---------------------------------------------------------------------------


class OrganizationRepositoryProtocol(Protocol):
    """Data access for organization records."""

    async def get(
        self,
        db: AsyncSession,
        id: UUID,
        ctx: Any = None,
        skip_access_validation: bool = False,
        enrich: bool = False,
    ) -> Optional[schemas.Organization]:
        """Return organization (enriched with billing/features when enrich=True)."""
        ...

    async def get_by_id(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        skip_access_validation: bool = False,
    ) -> Optional[Organization]:
        """Return organization ORM model by ID."""
        ...

    async def get_by_auth0_id(
        self,
        db: AsyncSession,
        *,
        auth0_org_id: str,
    ) -> Optional[Organization]:
        """Return organization ORM model by Auth0 org ID."""
        ...

    async def create_from_identity(
        self,
        db: AsyncSession,
        *,
        name: str,
        description: str,
        auth0_org_id: str,
    ) -> Organization:
        """Create an organization imported from an identity provider."""
        ...

    async def create_with_owner(
        self,
        db: AsyncSession,
        *,
        obj_in: schemas.OrganizationCreate,
        owner_user: User,
        uow: Optional[UnitOfWork] = None,
    ) -> Organization:
        """Create an organization and assign the owner."""
        ...

    async def delete(self, db: AsyncSession, *, organization_id: UUID) -> Organization:
        """Delete an organization by ID."""
        ...


class ApiKeyRepositoryProtocol(Protocol):
    """API key validation — org-scoped access tokens."""

    async def get_by_key(self, db: AsyncSession, *, key: str) -> Any:
        """Validate and return the API key ORM model.

        Raises:
            NotFoundException: If no matching key is found.
            PermissionException: If the key has expired or been revoked.
        """
        ...

    def record_usage(
        self,
        *,
        api_key_obj: Any,
        ip_address: str,
        endpoint: str,
        user_agent: Optional[str] = None,
    ) -> None:
        """Enqueue API key usage event for batch insertion."""
        ...

    def record_usage_by_id(
        self,
        *,
        api_key_id: UUID,
        organization_id: UUID,
        ip_address: str,
        endpoint: str,
        user_agent: Optional[str] = None,
    ) -> None:
        """Record usage from cached auth metadata (no ORM object needed)."""
        ...


class ApiKeyMaintenanceProtocol(Protocol):
    """Maintenance operations for API key lifecycle (Temporal activities)."""

    async def get_revoked_keys_older_than(
        self,
        db: AsyncSession,
        *,
        max_age_days: int = 90,
    ) -> list[APIKey]:
        """Return revoked keys older than the retention period."""
        ...

    async def expire_past_due_keys(self, db: AsyncSession) -> int:
        """Transition active keys past their expiration date to expired."""
        ...

    async def prune_usage_log(
        self,
        db: AsyncSession,
        *,
        max_age_days: int = 90,
        batch_size: int = 10_000,
    ) -> int:
        """Delete usage log entries older than the retention period."""
        ...

    async def get_keys_expiring_in_range(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime,
    ) -> list[APIKey]:
        """Return active keys expiring within a date range."""
        ...


class UserOrganizationRepositoryProtocol(Protocol):
    """Data access for user–organization membership records."""

    async def count_members(self, db: AsyncSession, organization_id: UUID) -> int:
        """Return member count for an organization."""
        ...

    async def get_membership(
        self, db: AsyncSession, *, org_id: UUID, user_id: UUID
    ) -> Optional[UserOrganization]:
        """Return membership record or None."""
        ...

    async def get_members_with_users(
        self, db: AsyncSession, *, organization_id: UUID
    ) -> list[tuple[User, str, bool]]:
        """Return ``(User, role, is_primary)`` tuples for all members."""
        ...

    async def get_owners(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        exclude_user_id: Optional[UUID] = None,
    ) -> list[UserOrganization]:
        """Return owner memberships for an organization."""
        ...

    async def get_user_memberships_with_orgs(
        self, db: AsyncSession, *, user_id: UUID
    ) -> list[schemas.OrganizationWithRole]:
        """Return organizations with roles for a user."""
        ...

    async def get_user_memberships_with_auth0_ids(
        self, db: AsyncSession, *, user_id: UUID
    ) -> list[tuple[UserOrganization, str | None]]:
        """Return ``(UserOrganization, auth0_org_id)`` for a user's memberships."""
        ...

    async def create(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        organization_id: UUID,
        role: str,
        is_primary: bool = False,
    ) -> UserOrganization:
        """Create a user-organization membership."""
        ...

    async def update_role(
        self, db: AsyncSession, *, user_id: UUID, organization_id: UUID, role: str
    ) -> bool:
        """Update the role for a user-organization membership."""
        ...

    async def delete_membership(
        self, db: AsyncSession, *, user_id: UUID, organization_id: UUID
    ) -> bool:
        """Delete a user-organization membership."""
        ...

    async def delete_all_for_org(self, db: AsyncSession, *, organization_id: UUID) -> list[str]:
        """Delete all memberships for an org; return affected user emails."""
        ...

    async def set_primary(self, db: AsyncSession, *, user_id: UUID, organization_id: UUID) -> bool:
        """Set an organization as primary for a user."""
        ...

    async def count_user_orgs(self, db: AsyncSession, *, user_id: UUID) -> int:
        """Return the number of organizations a user belongs to."""
        ...


# ---------------------------------------------------------------------------
# Service protocol (single facade consumed by API layer)
# ---------------------------------------------------------------------------


class OrganizationServiceProtocol(Protocol):
    """Combined organization service used by API endpoints.

    Covers org lifecycle, membership management, and user provisioning.
    """

    # --- Org lifecycle ---

    async def create_organization(
        self,
        db: AsyncSession,
        org_data: schemas.OrganizationCreate,
        owner_user: User,
    ) -> schemas.Organization:
        """Create an organization with the given owner."""
        ...

    async def delete_organization(
        self,
        db: AsyncSession,
        organization_id: UUID,
        deleting_user: User,
    ) -> bool:
        """Delete an organization."""
        ...

    # --- Membership ---

    async def invite_user(
        self,
        db: AsyncSession,
        organization_id: UUID,
        email: str,
        role: str,
        inviter_user: schemas.User,
    ) -> dict:
        """Invite a user to an organization."""
        ...

    async def remove_member(
        self,
        db: AsyncSession,
        organization_id: UUID,
        user_id: UUID,
        remover_user: User,
    ) -> bool:
        """Remove a member from an organization."""
        ...

    async def change_member_role(
        self,
        db: AsyncSession,
        organization_id: UUID,
        user_id: UUID,
        new_role: str,
    ) -> bool:
        """Change a member's role (Auth0 first, then local DB)."""
        ...

    async def leave_organization(
        self,
        db: AsyncSession,
        organization_id: UUID,
        leaving_user: User,
    ) -> bool:
        """Leave an organization."""
        ...

    async def get_members(self, db: AsyncSession, organization_id: UUID) -> list[dict]:
        """Return members of an organization."""
        ...

    async def get_pending_invitations(self, db: AsyncSession, organization_id: UUID) -> list[dict]:
        """Return pending invitations for an organization."""
        ...

    async def remove_invitation(
        self,
        db: AsyncSession,
        organization_id: UUID,
        invitation_id: str,
    ) -> bool:
        """Remove a pending invitation."""
        ...

    # --- Provisioning (used by users.py endpoint) ---

    async def provision_new_user(
        self, db: AsyncSession, user_data: dict, *, create_org: bool = False
    ) -> User:
        """Provision a new user, optionally creating an organization."""
        ...

    async def sync_user_organizations(self, db: AsyncSession, user: User) -> User:
        """Sync user organizations from the identity provider."""
        ...
