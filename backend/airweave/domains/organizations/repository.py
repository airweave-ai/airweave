"""Organization domain repositories.

Thin wrappers around CRUD singletons and direct queries. Keep data-access
concerns here so operations/services never write raw SQL.
"""

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.organization import Organization
from airweave.models.user import User
from airweave.models.user_organization import UserOrganization


class OrganizationRepository:
    """Delegates to the crud.organization singleton for org-level queries."""

    async def get(
        self,
        db: AsyncSession,
        id: UUID,
        ctx: Any = None,
        skip_access_validation: bool = False,
        enrich: bool = False,
    ) -> Optional[schemas.Organization]:
        """Return organization via delegated CRUD."""
        return await crud.organization.get(  # type: ignore[return-value]
            db, id, ctx=ctx, skip_access_validation=skip_access_validation, enrich=enrich
        )

    async def get_by_id(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        skip_access_validation: bool = False,
    ) -> Optional[Organization]:
        """Return organization ORM model by ID via delegated CRUD."""
        return await crud.organization.get(  # type: ignore[return-value]
            db, organization_id, skip_access_validation=skip_access_validation, enrich=False
        )

    async def create_with_owner(
        self,
        db: AsyncSession,
        *,
        obj_in: schemas.OrganizationCreate,
        owner_user: User,
        uow: Optional[UnitOfWork] = None,
    ) -> Organization:
        """Create organization with owner via delegated CRUD."""
        return await crud.organization.create_with_owner(
            db, obj_in=obj_in, owner_user=owner_user, uow=uow
        )

    async def delete(self, db: AsyncSession, *, organization_id: UUID) -> Organization:
        """Delete org without auto-commit (safe inside UoW)."""
        from sqlalchemy import delete as sa_delete

        stmt = select(Organization).where(Organization.id == organization_id)
        result = await db.execute(stmt)
        org = result.scalar_one_or_none()
        if not org:
            from airweave.core.exceptions import NotFoundException

            raise NotFoundException(f"Organization with ID {organization_id} not found")

        del_stmt = sa_delete(Organization).where(Organization.id == organization_id)
        await db.execute(del_stmt)
        return org


class UserOrganizationRepository:
    """Direct queries for user–organization memberships."""

    async def count_members(self, db: AsyncSession, organization_id: UUID) -> int:
        """Return member count for an organization."""
        stmt = (
            select(func.count())
            .select_from(UserOrganization)
            .where(UserOrganization.organization_id == organization_id)
        )
        result = await db.execute(stmt)
        return int(result.scalar_one() or 0)

    async def get_membership(
        self, db: AsyncSession, *, org_id: UUID, user_id: UUID
    ) -> Optional[UserOrganization]:
        """Return membership record or None."""
        stmt = select(UserOrganization).where(
            UserOrganization.user_id == user_id,
            UserOrganization.organization_id == org_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_members_with_users(
        self, db: AsyncSession, *, organization_id: UUID
    ) -> list[tuple[User, str, bool]]:
        """Return (User, role, is_primary) for all members of an org."""
        stmt = (
            select(User, UserOrganization.role, UserOrganization.is_primary)
            .join(UserOrganization, User.id == UserOrganization.user_id)
            .where(UserOrganization.organization_id == organization_id)
        )
        result = await db.execute(stmt)
        return list(result.all())  # type: ignore[arg-type]

    async def get_owners(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        exclude_user_id: Optional[UUID] = None,
    ) -> list[UserOrganization]:
        """Return owner memberships for an organization."""
        stmt = select(UserOrganization).where(
            UserOrganization.organization_id == organization_id,
            UserOrganization.role == "owner",
        )
        if exclude_user_id:
            stmt = stmt.where(UserOrganization.user_id != exclude_user_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_user_memberships_with_orgs(
        self, db: AsyncSession, *, user_id: UUID
    ) -> list[schemas.OrganizationWithRole]:
        """Return organizations with roles for a user via delegated CRUD."""
        return await crud.organization.get_user_organizations_with_roles(db, user_id=user_id)

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
        user_org = UserOrganization(
            user_id=user_id,
            organization_id=organization_id,
            role=role,
            is_primary=is_primary,
        )
        db.add(user_org)
        await db.flush()
        return user_org

    async def delete_membership(
        self, db: AsyncSession, *, user_id: UUID, organization_id: UUID
    ) -> bool:
        """Delete a user-organization membership."""
        stmt = delete(UserOrganization).where(
            UserOrganization.user_id == user_id,
            UserOrganization.organization_id == organization_id,
        )
        result = await db.execute(stmt)
        return result.rowcount > 0  # type: ignore[attr-defined, no-any-return]

    async def delete_all_for_org(self, db: AsyncSession, *, organization_id: UUID) -> list[str]:
        """Delete all memberships for org; return affected user emails for cache invalidation."""
        email_stmt = (
            select(User.email)
            .join(UserOrganization, User.id == UserOrganization.user_id)
            .where(UserOrganization.organization_id == organization_id)
        )
        result = await db.execute(email_stmt)
        emails = [row[0] for row in result.fetchall()]

        del_stmt = delete(UserOrganization).where(
            UserOrganization.organization_id == organization_id
        )
        await db.execute(del_stmt)
        return emails

    async def set_primary(self, db: AsyncSession, *, user_id: UUID, organization_id: UUID) -> bool:
        """Set an organization as primary for a user via delegated CRUD."""
        return await crud.organization.set_primary_organization(
            db,
            user_id=user_id,
            organization_id=organization_id,
            ctx=None,  # type: ignore[arg-type]
        )

    async def count_user_orgs(self, db: AsyncSession, *, user_id: UUID) -> int:
        """Return the number of organizations a user belongs to."""
        stmt = (
            select(func.count())
            .select_from(UserOrganization)
            .where(UserOrganization.user_id == user_id)
        )
        result = await db.execute(stmt)
        return int(result.scalar_one() or 0)


class ApiKeyRepository:
    """Delegates to crud.api_key for key validation."""

    async def get_by_key(self, db: AsyncSession, *, key: str) -> Any:
        """Validate and return the API key via delegated CRUD."""
        return await crud.api_key.get_by_key(db, key=key)
