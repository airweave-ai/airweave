"""User provisioning operations — signup flow and Auth0→local org sync.

Called from the ``users.py`` endpoint when a user logs in for the first
time or when an existing user's Auth0 organizations need syncing.
"""

from sqlalchemy import select
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
from airweave.models.organization import Organization
from airweave.models.user import User


class ProvisioningOperations:
    """Handles new-user signup and Auth0↔local org synchronization."""

    def __init__(
        self,
        *,
        org_repo: OrganizationRepositoryProtocol,
        user_org_repo: UserOrganizationRepositoryProtocol,
        identity_provider: IdentityProvider,
    ) -> None:
        """Initialize ProvisioningOperations."""
        self._org_repo = org_repo
        self._user_org_repo = user_org_repo
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
            if create_org:
                return await self._create_user_with_new_org(db, user_data)
            return await self._create_user_without_org(db, user_data)

    async def sync_user_organizations(self, db: AsyncSession, user: User) -> User:
        """Sync a user's identity provider organizations with local DB."""
        try:
            auth0_orgs = await self._identity.get_user_organizations(user.auth0_id)
            if not auth0_orgs:
                logger.info(f"User {user.email} has no identity provider orgs")
                return user

            logger.info(f"Syncing {len(auth0_orgs)} orgs for user {user.email}")
            for auth0_org in auth0_orgs:
                await self._sync_single_organization(db, user, auth0_org)

            await db.commit()
            await db.refresh(user)
            return user

        except Exception as e:
            logger.error(f"Failed to sync orgs for {user.email}: {e}")
            await db.rollback()
            return user

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _sync_single_organization(
        self, db: AsyncSession, user: User, auth0_org: dict
    ) -> None:
        """Sync one identity provider org → local DB."""
        query = select(Organization).where(Organization.auth0_org_id == auth0_org["id"])
        result = await db.execute(query)
        local_org = result.scalar_one_or_none()

        if not local_org:
            local_org = Organization(
                name=auth0_org.get("display_name", auth0_org["name"]),
                description=f"Imported from identity provider: {auth0_org['name']}",
                auth0_org_id=auth0_org["id"],
            )
            db.add(local_org)
            await db.flush()
            logger.info(f"Created local org for identity org: {auth0_org['id']}")

        # Check if user-org relationship already exists
        existing = await self._user_org_repo.get_membership(
            db, org_id=local_org.id, user_id=user.id
        )
        if existing:
            return

        is_primary = await self._user_org_repo.count_user_orgs(db, user_id=user.id) == 0

        member_roles = await self._identity.get_member_roles(
            org_id=auth0_org["id"], user_id=user.auth0_id
        )
        user_role = logic.determine_user_role(member_roles)

        await self._user_org_repo.create(
            db,
            user_id=user.id,
            organization_id=local_org.id,
            role=user_role,
            is_primary=is_primary,
        )
        logger.info(f"Created membership for user {user.id} in org {local_org.id} as {user_role}")

    async def _create_user_with_new_org(self, db: AsyncSession, user_data: dict) -> User:
        user_create = schemas.UserCreate(**user_data)
        user, _org = await crud.user.create_with_organization(db, obj_in=user_create)
        logger.info(f"Created user {user.email} with new org")
        return user

    async def _create_user_with_existing_orgs(
        self, db: AsyncSession, user_data: dict, auth0_orgs: list[dict]
    ) -> User:
        async with UnitOfWork(db) as uow:
            try:
                user_create = schemas.UserCreate(**user_data)
                user = User(**user_create.model_dump())
                db.add(user)
                await db.flush()

                for auth0_org in auth0_orgs:
                    await self._sync_single_organization(db, user, auth0_org)

                await uow.commit()
                await db.refresh(user)
                logger.info(f"Created user {user.email} and synced {len(auth0_orgs)} orgs")
                return user
            except Exception:
                await uow.rollback()
                raise

    async def _create_user_without_org(self, db: AsyncSession, user_data: dict) -> User:
        user_create = schemas.UserCreate(**user_data)
        user = User(**user_create.model_dump())
        db.add(user)
        await db.flush()
        await db.commit()
        await db.refresh(user)
        logger.info(f"Created user {user.email} without org")
        return user
