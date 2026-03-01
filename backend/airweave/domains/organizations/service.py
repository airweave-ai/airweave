"""Organization service — lifecycle, membership, and provisioning.

A single ``OrganizationServiceProtocol`` on the DI container, consumed by
both ``organizations.py`` and ``users.py`` endpoints.

Lifecycle (create/delete) is delegated to ``OrganizationLifecycleOperations``
because it has the heavy saga + compensation logic. Membership methods live
here directly — same deps, simple logic, no reason for a separate class.
Provisioning is delegated to ``ProvisioningOperations`` (different caller,
different concerns).
"""

from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.core.events.organization import OrganizationLifecycleEvent
from airweave.core.logging import logger
from airweave.core.protocols.event_bus import EventBus
from airweave.core.protocols.identity import IdentityProvider
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.organizations import logic
from airweave.domains.organizations.operations import OrganizationLifecycleOperations
from airweave.domains.organizations.protocols import (
    OrganizationRepositoryProtocol,
    UserOrganizationRepositoryProtocol,
)
from airweave.domains.organizations.provisioning.operations import ProvisioningOperations
from airweave.models.organization import Organization
from airweave.models.user import User


class OrganizationService:
    """Implements ``OrganizationServiceProtocol``."""

    def __init__(
        self,
        *,
        lifecycle_ops: OrganizationLifecycleOperations,
        provisioning_ops: ProvisioningOperations,
        org_repo: OrganizationRepositoryProtocol,
        user_org_repo: UserOrganizationRepositoryProtocol,
        identity_provider: IdentityProvider,
        event_bus: EventBus,
    ) -> None:
        """Initialize OrganizationService."""
        self._lifecycle = lifecycle_ops
        self._provisioning = provisioning_ops
        self._org_repo = org_repo
        self._user_org_repo = user_org_repo
        self._identity = identity_provider
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # Org lifecycle (delegated — heavy saga logic)
    # ------------------------------------------------------------------

    async def create_organization(
        self,
        db: AsyncSession,
        org_data: schemas.OrganizationCreate,
        owner_user: User,
    ) -> schemas.Organization:
        """Create organization via delegated lifecycle operations."""
        return await self._lifecycle.create_organization(db, org_data, owner_user)

    async def delete_organization(
        self,
        db: AsyncSession,
        organization_id: UUID,
        deleting_user: User,
    ) -> bool:
        """Delete organization via delegated lifecycle operations."""
        return await self._lifecycle.delete_organization(db, organization_id, deleting_user)

    # ------------------------------------------------------------------
    # Membership (inline — simple methods, same deps)
    # ------------------------------------------------------------------

    async def invite_user(
        self,
        db: AsyncSession,
        organization_id: UUID,
        email: str,
        role: str,
        inviter_user: schemas.User,
    ) -> dict:
        """Invite a user to an organization via identity provider."""
        org = await self._get_org(db, organization_id)
        invitation = await self._identity.invite_user(org.auth0_org_id, email, role, inviter_user)
        logger.info(f"Sent invitation to {email} for org {org.name}")
        return invitation

    async def remove_member(
        self,
        db: AsyncSession,
        organization_id: UUID,
        user_id: UUID,
        remover_user: User,
    ) -> bool:
        """Remove a member — local first, then identity provider.

        Local-first is safer: our DB is source of truth. If the identity
        provider call fails afterwards, the user is out of our DB (correct)
        but still in Auth0 (minor inconsistency, auto-syncs on next login).
        """
        from airweave.models.user import User as UserModel

        user_q = select(UserModel).where(UserModel.id == user_id)
        user_result = await db.execute(user_q)
        user_to_remove = user_result.scalar_one_or_none()
        if not user_to_remove:
            raise ValueError("User not found")

        org = await self._get_org(db, organization_id)
        user_schema = schemas.User.model_validate(user_to_remove)

        # Step 1: Local delete in UoW
        async with UnitOfWork(db) as uow:
            await self._user_org_repo.delete_membership(
                db, user_id=user_id, organization_id=organization_id
            )
            await uow.commit()

        # Step 2: Identity provider cleanup (best-effort, after local commit)
        if org.auth0_org_id and user_schema.auth0_id:
            try:
                await self._identity.remove_user_from_organization(
                    org.auth0_org_id, user_schema.auth0_id
                )
            except Exception as e:
                logger.warning(f"Failed to remove user from identity provider: {e}")

        # Step 3: Event
        await self._event_bus.publish(
            OrganizationLifecycleEvent.member_removed(
                organization_id=organization_id,
                organization_name=org.name,
                affected_user_emails=[user_schema.email],
            )
        )

        logger.info(f"Removed user {user_schema.email} from org {org.name}")
        return True

    async def leave_organization(
        self,
        db: AsyncSession,
        organization_id: UUID,
        leaving_user: User,
    ) -> bool:
        """Leave an organization by removing self as member."""
        return await self.remove_member(
            db, organization_id, cast(UUID, leaving_user.id), leaving_user
        )

    async def get_members(self, db: AsyncSession, organization_id: UUID) -> list[dict]:
        """Return members of an organization."""
        await self._get_org(db, organization_id)
        rows = await self._user_org_repo.get_members_with_users(db, organization_id=organization_id)
        return [
            {
                "id": str(user.id),
                "email": user.email,
                "name": user.full_name or user.email,
                "role": role,
                "status": "active",
                "is_primary": is_primary,
                "auth0_id": user.auth0_id,
            }
            for user, role, is_primary in rows
        ]

    async def get_pending_invitations(self, db: AsyncSession, organization_id: UUID) -> list[dict]:
        """Return pending invitations for an organization."""
        org = await self._get_org(db, organization_id)

        all_roles = await self._identity.get_roles()
        role_id_to_name = {r["id"]: r["name"] for r in all_roles}

        raw_invitations = await self._identity.get_pending_invitations(org.auth0_org_id)

        return [
            {
                "id": inv.get("id"),
                "email": inv.get("invitee", {}).get("email"),
                "role": logic.format_role_from_invitation(inv, role_id_to_name),
                "invited_at": inv.get("created_at"),
                "status": "pending",
            }
            for inv in raw_invitations
        ]

    async def remove_invitation(
        self,
        db: AsyncSession,
        organization_id: UUID,
        invitation_id: str,
    ) -> bool:
        """Remove a pending invitation from an organization."""
        org = await self._get_org(db, organization_id)
        await self._identity.delete_invitation(org.auth0_org_id, invitation_id)
        logger.info(f"Removed invitation {invitation_id} from org {org.name}")
        return True

    # ------------------------------------------------------------------
    # Provisioning (delegated — different caller, different concerns)
    # ------------------------------------------------------------------

    async def provision_new_user(
        self, db: AsyncSession, user_data: dict, *, create_org: bool = False
    ) -> User:
        """Provision new user via delegated provisioning operations."""
        return await self._provisioning.provision_new_user(db, user_data, create_org=create_org)

    async def sync_user_organizations(self, db: AsyncSession, user: User) -> User:
        """Sync user organizations via delegated provisioning operations."""
        return await self._provisioning.sync_user_organizations(db, user)

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    async def _get_org(self, db: AsyncSession, organization_id: UUID) -> Organization:
        org = await self._org_repo.get_by_id(
            db, organization_id=organization_id, skip_access_validation=True
        )
        if not org:
            raise ValueError("Organization not found")
        return org
