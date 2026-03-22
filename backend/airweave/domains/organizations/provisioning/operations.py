"""User provisioning operations — signup flow and Auth0→local org sync.

Called from the ``users.py`` endpoint when a user logs in for the first
time or when an existing user's Auth0 organizations need syncing.
"""

from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.logging import logger
from airweave.core.protocols.identity import IdentityProvider
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.organizations import logic
from airweave.domains.organizations.protocols import (
    OrganizationRepositoryProtocol,
    UserOrganizationRepositoryProtocol,
)
from airweave.domains.users.protocols import UserRepositoryProtocol
from airweave.models.user import User


class ProvisioningOperations:
    """Handles new-user signup and Auth0↔local org synchronization."""

    def __init__(
        self,
        *,
        org_repo: OrganizationRepositoryProtocol,
        user_org_repo: UserOrganizationRepositoryProtocol,
        user_repo: UserRepositoryProtocol,
        identity_provider: IdentityProvider,
    ) -> None:
        """Initialize ProvisioningOperations."""
        self._org_repo = org_repo
        self._user_org_repo = user_org_repo
        self._user_repo = user_repo
        self._identity = identity_provider

    async def provision_new_user(
        self, db: AsyncSession, user_data: dict, *, create_org: bool = False
    ) -> User:
        """Handle new user signup — check identity provider orgs and sync.

        Args:
            db: Database session.
            user_data: Dict with user fields (email, auth0_id, etc.).
            create_org: Whether to auto-create an org when none exist.
        """
        auth0_id = user_data.get("auth0_id")
        if not auth0_id:
            raise ValueError("No Auth0 ID provided")

        try:
            auth0_orgs = await self._identity.get_user_organizations(auth0_id)

            if auth0_orgs:
                logger.info(
                    f"User {user_data.get('email')} has {len(auth0_orgs)} identity provider orgs"
                )
                return await self._create_user_with_existing_orgs(db, user_data, auth0_orgs)

            if create_org:
                logger.info(f"User {user_data.get('email')} has no orgs — creating new")
                return await self._create_user_with_new_org(db, user_data)

            logger.info(f"User {user_data.get('email')} has no orgs — creating without")
            return await self._create_user_without_org(db, user_data)

        except Exception as e:
            logger.error(f"Failed to check identity orgs for new user: {e}")
            async with UnitOfWork(db):
                pass  # UoW context manager handles rollback of dirty session
            if create_org:
                return await self._create_user_with_new_org(db, user_data)
            return await self._create_user_without_org(db, user_data)

    async def sync_user_organizations(self, db: AsyncSession, user: User) -> User:
        """Sync a user's identity provider organizations with local DB.

        Auth0 is the source of truth:
        1. Add memberships that exist in Auth0 but not locally.
        2. Remove local memberships whose org's auth0_org_id is NOT in Auth0.
        3. Update roles if Auth0 role differs from local role.
        """
        user_email = user.email
        user_auth0_id = user.auth0_id
        user_id = cast(UUID, user.id)
        try:
            auth0_orgs = await self._identity.get_user_organizations(user_auth0_id)
            auth0_org_ids = {org["id"] for org in auth0_orgs} if auth0_orgs else set()

            logger.info(
                f"Syncing orgs for user {user_email}: {len(auth0_org_ids)} in identity provider"
            )

            async with UnitOfWork(db) as uow:
                for auth0_org in auth0_orgs or []:
                    await self._sync_single_organization(
                        db, user_id=user_id, user_auth0_id=user_auth0_id, auth0_org=auth0_org
                    )

                local_memberships = await self._user_org_repo.get_user_memberships_with_auth0_ids(
                    db, user_id=user_id
                )
                for membership, local_auth0_org_id in local_memberships:
                    if local_auth0_org_id and local_auth0_org_id not in auth0_org_ids:
                        await self._user_org_repo.delete_membership(
                            db,
                            user_id=user_id,
                            organization_id=cast(UUID, membership.organization_id),
                        )
                        logger.info(
                            f"Removed stale membership for user {user_email} "
                            f"in org {membership.organization_id} "
                            f"(auth0_org {local_auth0_org_id} not in identity provider)"
                        )

                await uow.commit()

            return await self._user_repo.refresh(db, user=user)

        except Exception as e:
            logger.error(f"Failed to sync orgs for {user_email}: {e}")
            return user

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _sync_single_organization(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        user_auth0_id: str,
        auth0_org: dict,
    ) -> None:
        """Sync one identity provider org → local DB (add or update role).

        Accepts pre-extracted scalars instead of the User ORM model to avoid
        lazy-load greenlet errors when the session expires the model mid-UoW.
        """
        local_org = await self._org_repo.get_by_auth0_id(db, auth0_org_id=auth0_org["id"])

        if not local_org:
            local_org = await self._org_repo.create_from_identity(
                db,
                name=auth0_org.get("display_name", auth0_org["name"]),
                description=f"Imported from identity provider: {auth0_org['name']}",
                auth0_org_id=auth0_org["id"],
            )
            logger.info(f"Created local org for identity org: {auth0_org['id']}")

        local_org_id = cast(UUID, local_org.id)

        member_roles = await self._identity.get_member_roles(
            org_id=auth0_org["id"], user_id=user_auth0_id
        )
        auth0_role = logic.determine_user_role(member_roles)

        existing = await self._user_org_repo.get_membership(
            db, org_id=local_org_id, user_id=user_id
        )
        if existing:
            if existing.role != auth0_role:
                await self._user_org_repo.update_role(
                    db,
                    user_id=user_id,
                    organization_id=local_org_id,
                    role=auth0_role,
                )
                logger.info(
                    f"Updated role for user {user_id} in org {local_org.id}: "
                    f"{existing.role} → {auth0_role}"
                )
            return

        is_primary = await self._user_org_repo.count_user_orgs(db, user_id=user_id) == 0

        await self._user_org_repo.create(
            db,
            user_id=user_id,
            organization_id=local_org_id,
            role=auth0_role,
            is_primary=is_primary,
        )
        logger.info(f"Created membership for user {user_id} in org {local_org_id} as {auth0_role}")

    async def _create_user_with_new_org(self, db: AsyncSession, user_data: dict) -> User:
        user_create = schemas.UserCreate(**user_data)
        schema_user, _org = await crud.user.create_with_organization(db, obj_in=user_create)
        logger.info(f"Created user {schema_user.email} with new org")
        return cast(User, schema_user)

    async def _create_user_with_existing_orgs(
        self, db: AsyncSession, user_data: dict, auth0_orgs: list[dict]
    ) -> User:
        async with UnitOfWork(db) as uow:
            try:
                user_create = schemas.UserCreate(**user_data)
                user = await self._user_repo.create(db, obj_in=user_create)

                uid = cast(UUID, user.id)
                auth0_id = user.auth0_id

                for auth0_org in auth0_orgs:
                    await self._sync_single_organization(
                        db, user_id=uid, user_auth0_id=auth0_id, auth0_org=auth0_org
                    )

                await uow.commit()
                user = await self._user_repo.refresh(db, user=user)
                logger.info(f"Created user {user.email} and synced {len(auth0_orgs)} orgs")
                return user
            except Exception:
                await uow.rollback()
                raise

    async def _create_user_without_org(self, db: AsyncSession, user_data: dict) -> User:
        async with UnitOfWork(db) as uow:
            user_create = schemas.UserCreate(**user_data)
            user = await self._user_repo.create(db, obj_in=user_create)
            await uow.commit()
        user = await self._user_repo.refresh(db, user=user)
        logger.info(f"Created user {user.email} without org")
        return user
