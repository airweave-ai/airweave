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
    OrganizationServiceProtocol,
    UserOrganizationRepositoryProtocol,
)
from airweave.domains.organizations.provisioning.operations import ProvisioningOperations
from airweave.models.organization import Organization
from airweave.models.user import User


class OrganizationService(OrganizationServiceProtocol):
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
        """Remove a member — Auth0 first (source of truth), then local DB.

        Auth0-first prevents "user resurrection": if Auth0 removal succeeds,
        the user won't be re-synced on next login even if the DB delete fails.
        404 from Auth0 is treated as already-removed (idempotent).
        If the DB delete fails after Auth0 succeeds, we compensate by
        re-adding the user to Auth0.
        """
        from airweave.models.user import User as UserModel

        user_q = select(UserModel).where(UserModel.id == user_id)
        user_result = await db.execute(user_q)
        user_to_remove = user_result.scalar_one_or_none()
        if not user_to_remove:
            raise ValueError("User not found")

        org = await self._get_org(db, organization_id)
        org_name = org.name
        org_auth0_id = org.auth0_org_id
        user_schema = schemas.User.model_validate(user_to_remove)

        # Step 1: Identity provider removal (source of truth, fail-fast)
        if org_auth0_id and user_schema.auth0_id:
            await self._identity.remove_user_from_organization(org_auth0_id, user_schema.auth0_id)

        # Step 2: Local delete in UoW
        try:
            async with UnitOfWork(db) as uow:
                await self._user_org_repo.delete_membership(
                    db, user_id=user_id, organization_id=organization_id
                )
                await uow.commit()
        except Exception:
            if org_auth0_id and user_schema.auth0_id:
                try:
                    await self._identity.add_user_to_organization(
                        org_auth0_id, user_schema.auth0_id
                    )
                    logger.info(
                        f"Compensated: re-added {user_schema.email} to Auth0 org after DB failure"
                    )
                except Exception as comp_err:
                    logger.critical(
                        f"COMPENSATION FAILED: user {user_schema.email} removed from "
                        f"Auth0 org {org_auth0_id} but DB delete failed and "
                        f"re-add also failed: {comp_err}"
                    )
            raise

        # Step 3: Event
        await self._event_bus.publish(
            OrganizationLifecycleEvent.member_removed(
                organization_id=organization_id,
                organization_name=org_name,
                affected_user_emails=[user_schema.email],
            )
        )

        logger.info(f"Removed user {user_schema.email} from org {org_name}")
        return True

    async def change_member_role(
        self,
        db: AsyncSession,
        organization_id: UUID,
        user_id: UUID,
        new_role: str,
    ) -> bool:
        """Change a member's role — Auth0 first (source of truth), then local DB.

        If the DB update fails after Auth0 succeeds, we compensate by
        restoring the old Auth0 role.
        """
        from airweave.models.user import User as UserModel

        user_q = select(UserModel).where(UserModel.id == user_id)
        user_result = await db.execute(user_q)
        target_user = user_result.scalar_one_or_none()
        if not target_user:
            raise ValueError("User not found")

        org = await self._get_org(db, organization_id)
        target_email = target_user.email
        target_auth0_id = target_user.auth0_id
        org_name = org.name
        org_auth0_id = org.auth0_org_id

        membership = await self._user_org_repo.get_membership(
            db, org_id=organization_id, user_id=user_id
        )
        if not membership:
            raise ValueError("User is not a member of this organization")

        old_role = membership.role
        if old_role == new_role:
            return True

        # Step 1: Update Auth0 roles (source of truth)
        if org_auth0_id and target_auth0_id:
            all_roles = await self._identity.get_roles()
            role_id = next((r["id"] for r in all_roles if r["name"] == new_role), None)
            if role_id:
                await self._identity.set_member_roles(org_auth0_id, target_auth0_id, [role_id])

        # Step 2: Update local DB
        try:
            async with UnitOfWork(db) as uow:
                await self._user_org_repo.update_role(
                    db, user_id=user_id, organization_id=organization_id, role=new_role
                )
                await uow.commit()
        except Exception:
            if org_auth0_id and target_auth0_id:
                try:
                    all_roles = await self._identity.get_roles()
                    old_role_id = next((r["id"] for r in all_roles if r["name"] == old_role), None)
                    if old_role_id:
                        await self._identity.set_member_roles(
                            org_auth0_id, target_auth0_id, [old_role_id]
                        )
                except Exception as comp_err:
                    logger.critical(
                        f"COMPENSATION FAILED: role for {target_email} changed to "
                        f"{new_role} in Auth0 but DB update failed and rollback also "
                        f"failed: {comp_err}"
                    )
            raise

        logger.info(f"Changed role for {target_email} in org {org_name}: {old_role} → {new_role}")
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
    ) -> schemas.User:
        """Provision new user via delegated provisioning operations."""
        return await self._provisioning.provision_new_user(db, user_data, create_org=create_org)

    async def sync_user_organizations(self, db: AsyncSession, user: schemas.User) -> schemas.User:
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
