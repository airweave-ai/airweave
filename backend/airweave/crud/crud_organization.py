"""CRUD operations for the organization model."""

from typing import Any, List, Optional, Union
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from airweave import schemas
from airweave.core.context import BaseContext
from airweave.core.exceptions import NotFoundException, PermissionException
from airweave.core.logging import logger
from airweave.core.shared_models import FeatureFlag as FeatureFlagEnum
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.feature_flag import FeatureFlag
from airweave.models.organization import Organization
from airweave.models.user import User
from airweave.models.user_organization import UserOrganization
from airweave.schemas.organization import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationWithRole,
)


class CRUDOrganization:
    """CRUD operations for the organization model.

    Note: This handles Organization entities themselves, not organization-scoped resources.
    Organizations don't have organization_id (they ARE organizations), so this class
    implements its own validation logic rather than inheriting from CRUDBaseOrganization.
    """

    def __init__(self):
        """Initialize the Organization CRUD."""
        self.model = Organization

    def _extract_enabled_features(self, org: Organization) -> List[FeatureFlagEnum]:
        """Extract enabled features from organization model.

        Args:
            org: Organization model with feature_flags loaded

        Returns:
            List of enabled FeatureFlag enums
        """
        # feature_flags should be loaded via selectin, check __dict__ to avoid lazy loading
        if "feature_flags" in org.__dict__:
            return [FeatureFlagEnum(ff.flag) for ff in org.__dict__["feature_flags"] if ff.enabled]
        return []

    async def _enrich_with_billing_and_period(
        self, db: AsyncSession, org: Organization
    ) -> schemas.Organization:
        """Enrich organization with billing info and current period.

        This method loads the billing relationship and current period, then returns
        a fully enriched schemas.Organization object suitable for caching.

        Args:
            db: Database session
            org: Organization model (with feature_flags already loaded)

        Returns:
            Enriched Organization schema with billing and current period
        """
        from airweave import crud

        # Convert to schema first (this handles feature flags via model_validator)
        org_schema = schemas.Organization.model_validate(org, from_attributes=True)

        # Load billing if present (OSS installs may not have billing)
        if "billing" in org.__dict__ and org.__dict__["billing"]:
            billing_model = org.__dict__["billing"]

            # Get current billing period
            current_period = await crud.billing_period.get_current_period(
                db, organization_id=org.id
            )

            # Create billing schema with current period
            billing_schema = schemas.OrganizationBilling.model_validate(
                billing_model, from_attributes=True
            )

            # Attach current period if found
            if current_period:
                billing_schema.current_period = schemas.BillingPeriod.model_validate(
                    current_period, from_attributes=True
                )

            # Attach enriched billing to organization
            org_schema.billing = billing_schema

        return org_schema

    async def get_by_auth0_id(
        self, db: AsyncSession, auth0_org_id: str, enrich: bool = True
    ) -> Union[Organization, schemas.Organization, None]:
        """Get an organization by its Auth0 organization ID.

        Args:
            db: Database session
            auth0_org_id: Auth0 organization ID
            enrich: If True, return enriched schemas.Organization with billing and period

        Returns:
            Organization model, enriched schema, or None
        """
        stmt = (
            select(Organization)
            .where(Organization.auth0_org_id == auth0_org_id)
            .options(
                selectinload(Organization.feature_flags),
                selectinload(Organization.billing),
            )
        )
        result = await db.execute(stmt)
        db_obj = result.scalar_one_or_none()

        if db_obj and enrich:
            return await self._enrich_with_billing_and_period(db, db_obj)

        return db_obj

    async def _set_primary_organization(
        self, db: AsyncSession, user_id: UUID, organization_id: UUID
    ) -> None:
        """Set an organization as primary for a user, ensuring only one is primary.

        Args:
            db: Database session
            user_id: The user's ID
            organization_id: The organization ID to set as primary
        """
        # Log for debugging
        logger.info(
            f"Setting primary organization for user {user_id} to organization {organization_id}"
        )

        # First, directly update ALL user organizations to set is_primary=False
        stmt_clear_all = (
            update(UserOrganization)
            .where(UserOrganization.user_id == user_id)
            .values(is_primary=False)
        )
        await db.execute(stmt_clear_all)
        await db.flush()

        # Then set the specific organization as primary
        stmt_set_primary = (
            update(UserOrganization)
            .where(
                UserOrganization.user_id == user_id,
                UserOrganization.organization_id == organization_id,
            )
            .values(is_primary=True)
        )
        result = await db.execute(stmt_set_primary)

        if result.rowcount == 0:
            raise NotFoundException(
                f"User with ID {user_id} not found in organization with ID {organization_id}"
            )

        await db.flush()
        logger.info(
            f"Successfully set organization {organization_id} as primary for user {user_id}"
        )

    async def set_primary_organization(
        self, db: AsyncSession, user_id: UUID, organization_id: UUID, ctx: BaseContext
    ) -> bool:
        """Set an organization as primary for a user with access validation.

        Args:
            db: Database session
            user_id: The user's ID
            organization_id: The organization ID to set as primary
            ctx: The API context

        Returns:
            True if successful, False if the user doesn't have access to the organization
        """
        # Validate the user has access to this organization
        user_org = await self.get_user_membership(
            db=db, organization_id=organization_id, user_id=user_id, ctx=ctx
        )

        if not user_org:
            raise NotFoundException(
                f"User with ID {user_id} not found in organization with ID {organization_id}"
            )

        await self._set_primary_organization(db, user_id, organization_id)
        await db.commit()
        return True

    async def create_with_owner(
        self,
        db: AsyncSession,
        *,
        obj_in: OrganizationCreate,
        owner_user: User,
        uow: Optional[UnitOfWork] = None,
    ) -> Organization:
        """Create organization and assign the user as owner.

        Args:
            db: Database session
            obj_in: Organization creation data
            owner_user: User who will become the owner
            uow: Unit of work

        Returns:
            The created organization
        """
        # Use the full obj_in data to preserve all fields including auth0_org_id
        if not isinstance(obj_in, dict):
            org_data_dict = obj_in.model_dump(exclude_unset=True)
        else:
            org_data_dict = obj_in

        organization = Organization(**org_data_dict)
        db.add(organization)
        await db.flush()  # Get the ID

        # Check if user has any existing organizations
        stmt = select(UserOrganization).where(UserOrganization.user_id == owner_user.id)
        result = await db.execute(stmt)
        existing_orgs = result.scalars().all()

        # New organization is primary if it's the user's first organization
        is_primary = len(existing_orgs) == 0

        # Create UserOrganization relationship with owner role
        user_org = UserOrganization(
            user_id=owner_user.id,
            organization_id=organization.id,
            role="owner",
            is_primary=is_primary,
        )
        db.add(user_org)

        # If this is the primary organization, ensure no other org is primary
        if is_primary:
            await db.flush()  # Ensure user_org is persisted before calling helper
            await self._set_primary_organization(db, owner_user.id, organization.id)

        if not uow:
            await db.commit()
            await db.refresh(organization)

        return organization

    async def get(
        self,
        db: AsyncSession,
        id: UUID,
        ctx: Optional[BaseContext] = None,
        skip_access_validation: bool = False,
        enrich: bool = True,
    ) -> Optional[Union[Organization, schemas.Organization]]:
        """Get organization by ID with access validation.

        Organizations don't have organization_id field, so we override the base method.

        Args:
            db: Database session
            id: Organization ID
            ctx: API context for access validation
            skip_access_validation: Skip access check (internal use)
            enrich: If True, return enriched schemas.Organization with billing and period

        Returns:
            Organization model or enriched schema depending on enrich parameter
        """
        # Check if the user has access to this organization
        if not skip_access_validation:
            if not ctx:
                raise PermissionException("No context provided")
            await self._validate_organization_access(ctx, id)

        query = (
            select(self.model)
            .where(self.model.id == id)
            .options(
                selectinload(Organization.feature_flags),
                selectinload(Organization.billing),
            )
        )
        result = await db.execute(query)
        db_obj = result.unique().scalar_one_or_none()
        if not db_obj:
            raise NotFoundException(f"Organization with ID {id} not found")

        # Return enriched schema with billing and current period if requested
        if enrich:
            return await self._enrich_with_billing_and_period(db, db_obj)

        return db_obj

    async def get_multi(
        self,
        db: AsyncSession,
        ctx: BaseContext,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Organization]:
        """Get all organizations for the authenticated user/API key.

        Organizations don't have organization_id field, so we override the base method.
        """
        if ctx.has_user_context:
            # Get organizations the user has access to
            user_org_ids = [org.organization.id for org in ctx.user.user_organizations]
            if not user_org_ids:
                return []

            query = (
                select(self.model)
                .where(self.model.id.in_(user_org_ids))
                .options(selectinload(Organization.feature_flags))
                .offset(skip)
                .limit(limit)
            )
        else:
            # For API key access, only return the key's organization
            query = (
                select(self.model)
                .where(self.model.id == ctx.organization.id)
                .options(selectinload(Organization.feature_flags))
                .offset(skip)
                .limit(limit)
            )

        result = await db.execute(query)
        return list(result.unique().scalars().all())

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: Organization,
        obj_in: Union[OrganizationUpdate, dict[str, Any]],
        ctx: BaseContext,
        uow: Optional[UnitOfWork] = None,
    ) -> Organization:
        """Update organization with access validation.

        Organizations don't have organization_id field, so we override the base method.
        """
        # Check if the user has access to this organization
        if ctx.has_user_context:
            user_org_ids = [org.organization.id for org in ctx.user.user_organizations]
            if db_obj.id not in user_org_ids:
                from airweave.core.exceptions import PermissionException

                raise PermissionException("User does not have access to organization")
        else:
            # For API key access, only allow access to the key's organization
            if db_obj.id != ctx.organization.id:
                from airweave.core.exceptions import PermissionException

                raise PermissionException("API key does not have access to organization")

        if not isinstance(obj_in, dict):
            obj_in = obj_in.model_dump(exclude_unset=True)

        # Organizations track user modifications
        if ctx.has_user_context:
            obj_in["modified_by_email"] = ctx.tracking_email

        for field, value in obj_in.items():
            setattr(db_obj, field, value)

        if not uow:
            await db.commit()
            await db.refresh(db_obj)

        return db_obj

    async def create(db, obj_in, ctx) -> NotImplementedError:
        """Create organization resource with auth context."""
        raise NotImplementedError("This method is not implemented for organizations.")

    async def _validate_organization_access(self, ctx: BaseContext, organization_id: UUID) -> None:
        """Validate auth context has access to organization.

        Args:
        ----
            ctx (BaseContext): The API context.
            organization_id (UUID): The organization ID to validate access to.

        Raises:
        ------
            PermissionException: If auth context does not have access to organization.
        """
        if ctx.has_user_context:
            # Admin users bypass organization access validation
            if ctx.user.is_admin:
                return

            if organization_id not in [org.organization.id for org in ctx.user.user_organizations]:
                raise PermissionException("User does not have access to organization")
        else:
            if organization_id != ctx.organization.id:  # type: ignore
                raise PermissionException("API key does not have access to organization")

    async def get_user_organizations_with_roles(
        self, db: AsyncSession, user_id: UUID
    ) -> List[OrganizationWithRole]:
        """Get all organizations for a user with their roles.

        Args:
            db: Database session
            user_id: The user's ID

        Returns:
            List of organizations with user's role information
        """
        stmt = (
            select(Organization, UserOrganization.role, UserOrganization.is_primary)
            .join(UserOrganization, Organization.id == UserOrganization.organization_id)
            .where(UserOrganization.user_id == user_id)
            .options(selectinload(Organization.feature_flags))
            .order_by(UserOrganization.is_primary.desc(), Organization.name)
        )

        result = await db.execute(stmt)
        rows = result.all()

        return [
            OrganizationWithRole(
                id=org.id,
                name=org.name,
                description=org.description or "",
                created_at=org.created_at,
                modified_at=org.modified_at,
                role=role,
                is_primary=is_primary,
                auth0_org_id=org.auth0_org_id,
                org_metadata=org.org_metadata,
                enabled_features=self._extract_enabled_features(org),
            )
            for org, role, is_primary in rows
        ]

    async def _validate_admin_access(
        self, ctx: BaseContext, organization_id: UUID
    ) -> UserOrganization:
        """Validate user has admin/owner access to organization.

        Args:
            ctx: The API context
            organization_id: Organization ID to validate admin access to

        Returns:
            UserOrganization record for the user

        Raises:
            HTTPException: If user doesn't have admin access
        """
        from fastapi import HTTPException

        # First validate basic organization access
        await self._validate_organization_access(ctx, organization_id)

        # Then check if user is admin/owner by finding their UserOrganization record
        if not ctx.has_user_context:
            raise HTTPException(status_code=403, detail="API keys cannot perform admin actions")

        # Find the user's role in this organization
        user_org = None
        for org in ctx.user.user_organizations:
            if org.organization.id == organization_id:
                user_org = org
                break

        if not user_org or user_org.role not in ["owner", "admin"]:
            raise HTTPException(
                status_code=403,
                detail="You must be an admin or owner to perform this action",
            )

        return user_org

    async def get_user_membership(
        self, db: AsyncSession, organization_id: UUID, user_id: UUID, ctx: BaseContext
    ) -> Optional[UserOrganization]:
        """Get user membership in organization with access validation.

        Args:
            db: Database session
            organization_id: The organization's ID
            user_id: The user's ID to check membership for
            ctx: Current authenticated user

        Returns:
            UserOrganization record if found, None otherwise
        """
        # Validate current user has access to this organization
        await self._validate_organization_access(ctx, organization_id)

        # Query the membership
        stmt = select(UserOrganization).where(
            UserOrganization.user_id == user_id,
            UserOrganization.organization_id == organization_id,
        )
        result = await db.execute(stmt)
        db_obj = result.scalar_one_or_none()
        if not db_obj:
            raise NotFoundException(
                f"User with ID {user_id} not found in organization with ID {organization_id}"
            )
        return db_obj

    async def get_organization_owners(
        self,
        db: AsyncSession,
        organization_id: UUID,
        ctx: BaseContext,
        exclude_user_id: Optional[UUID] = None,
    ) -> List[UserOrganization]:
        """Get all owners of an organization with access validation.

        Args:
            db: Database session
            organization_id: The organization's ID
            ctx: The auth context
            exclude_user_id: Optional user ID to exclude from results

        Returns:
            List of UserOrganization records with owner role
        """
        # Validate current user has access to this organization
        await self._validate_organization_access(ctx, organization_id)

        stmt = select(UserOrganization).where(
            UserOrganization.organization_id == organization_id,
            UserOrganization.role == "owner",
        )

        if exclude_user_id:
            stmt = stmt.where(UserOrganization.user_id != exclude_user_id)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_organization_members(
        self, db: AsyncSession, organization_id: UUID, ctx: BaseContext
    ) -> List[UserOrganization]:
        """Get all members of an organization with access validation.

        Args:
            db: Database session
            organization_id: The organization's ID
            ctx: The auth context

        Returns:
            List of UserOrganization records for the organization
        """
        # Validate current user has access to this organization
        await self._validate_organization_access(ctx, organization_id)

        stmt = (
            select(UserOrganization)
            .where(UserOrganization.organization_id == organization_id)
            .order_by(UserOrganization.role.desc(), UserOrganization.user_id)
        )

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def remove_member(
        self, db: AsyncSession, organization_id: UUID, user_id: UUID, ctx: BaseContext
    ) -> bool:
        """Remove a user from an organization with proper permission checks.

        Args:
            db: Database session
            organization_id: The organization's ID
            user_id: The user's ID to remove
            ctx: Current authentication context

        Returns:
            True if the relationship was removed, False if it didn't exist

        Raises:
            HTTPException: If current user doesn't have permission
        """
        from fastapi import HTTPException

        # If user is trying to remove themselves, we allow it with different validation
        if user_id == ctx.user.id:
            user_org = await self.get_user_membership(db, organization_id, user_id, ctx)

            # If they're an owner, check if there are other owners
            if user_org.role == "owner":
                owners = await self.get_organization_owners(
                    db, organization_id, ctx, exclude_user_id=user_id
                )
                if not owners:
                    raise HTTPException(
                        status_code=400,
                        detail="Cannot remove yourself as the only owner. "
                        "Transfer ownership to another member first.",
                    )
        else:
            # If removing someone else, validate current user has admin access
            await self._validate_admin_access(ctx, organization_id)

        stmt = delete(UserOrganization).where(
            UserOrganization.user_id == user_id,
            UserOrganization.organization_id == organization_id,
        )

        result = await db.execute(stmt)
        await db.commit()

        return result.rowcount > 0

    async def add_member(
        self,
        db: AsyncSession,
        organization_id: UUID,
        user_id: UUID,
        role: str,
        ctx: BaseContext,
        is_primary: bool = False,
    ) -> UserOrganization:
        """Add a user to an organization with proper permission checks.

        Args:
            db: Database session
            organization_id: The organization's ID
            user_id: The user's ID to add
            role: The user's role in the organization
            ctx: Current authenticated user
            is_primary: Whether this is the user's primary organization

        Returns:
            The created UserOrganization record

        Raises:
            HTTPException: If current user doesn't have permission
        """
        # Validate current user has admin access
        await self._validate_admin_access(ctx, organization_id)

        # Check if user already has organizations
        stmt = select(UserOrganization).where(UserOrganization.user_id == user_id)
        result = await db.execute(stmt)
        existing_orgs = result.scalars().all()

        # If this is their first organization, make it primary regardless of the parameter
        if len(existing_orgs) == 0:
            is_primary = True

        user_org = UserOrganization(
            user_id=user_id,
            organization_id=organization_id,
            role=role,
            is_primary=is_primary,
        )

        db.add(user_org)
        await db.flush()

        # If setting as primary, ensure no other org is primary for this user
        if is_primary:
            await self._set_primary_organization(db, user_id, organization_id)

        await db.commit()
        await db.refresh(user_org)

        return user_org

    async def update_member_role(
        self,
        db: AsyncSession,
        organization_id: UUID,
        user_id: UUID,
        new_role: str,
        ctx: BaseContext,
    ) -> Optional[UserOrganization]:
        """Update a user's role in an organization with proper permission checks.

        Args:
            db: Database session
            organization_id: The organization's ID
            user_id: The user's ID whose role to update
            new_role: The new role for the user
            ctx: Current authenticated user

        Returns:
            The updated UserOrganization record if found, None otherwise

        Raises:
            HTTPException: If current user doesn't have permission
        """
        # Validate current user has admin access
        await self._validate_admin_access(ctx, organization_id)

        user_org = await self.get_user_membership(db, organization_id, user_id, ctx)

        if user_org:
            user_org.role = new_role
            await db.commit()
            await db.refresh(user_org)

        return user_org

    async def remove(self, db: AsyncSession, id: UUID) -> Organization:
        """Remove an organization."""
        # First get the organization to return it
        get_stmt = select(Organization).where(Organization.id == id)
        get_result = await db.execute(get_stmt)
        org_to_delete = get_result.scalar_one_or_none()

        if org_to_delete is None:
            from airweave.core.exceptions import NotFoundException

            raise NotFoundException(f"Organization with ID {id} not found")

        # Then delete it
        delete_stmt = delete(Organization).where(Organization.id == id)
        await db.execute(delete_stmt)
        await db.commit()

        return org_to_delete

    # Feature Flag Management Methods

    async def enable_feature(
        self, db: AsyncSession, organization_id: UUID, flag: FeatureFlagEnum
    ) -> FeatureFlag:
        """Enable a feature flag for an organization.

        Args:
            db: Database session
            organization_id: Organization ID
            flag: Feature flag to enable

        Returns:
            FeatureFlag instance
        """
        # Check if flag already exists
        stmt = select(FeatureFlag).where(
            FeatureFlag.organization_id == organization_id,
            FeatureFlag.flag == flag.value,
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Update to enabled if it was disabled
            if not existing.enabled:
                existing.enabled = True
                await db.commit()
                await db.refresh(existing)
            return existing

        # Create new flag
        flag_obj = FeatureFlag(organization_id=organization_id, flag=flag.value, enabled=True)
        db.add(flag_obj)
        await db.commit()
        await db.refresh(flag_obj)
        return flag_obj

    async def disable_feature(
        self, db: AsyncSession, organization_id: UUID, flag: FeatureFlagEnum
    ) -> None:
        """Disable a feature flag for an organization.

        Args:
            db: Database session
            organization_id: Organization ID
            flag: Feature flag to disable
        """
        stmt = select(FeatureFlag).where(
            FeatureFlag.organization_id == organization_id,
            FeatureFlag.flag == flag.value,
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.enabled = False
            await db.commit()

    async def get_org_features(
        self, db: AsyncSession, organization_id: UUID
    ) -> List[FeatureFlagEnum]:
        """Get all enabled feature flags for an organization.

        Args:
            db: Database session
            organization_id: Organization ID

        Returns:
            List of enabled FeatureFlag enums
        """
        stmt = select(FeatureFlag).where(
            FeatureFlag.organization_id == organization_id,
            FeatureFlag.enabled == True,  # noqa: E712
        )
        result = await db.execute(stmt)
        flags = result.scalars().all()
        return [FeatureFlagEnum(f.flag) for f in flags]

    async def bulk_enable_features(
        self, db: AsyncSession, organization_id: UUID, flags: List[FeatureFlagEnum]
    ) -> List[FeatureFlag]:
        """Enable multiple feature flags for an organization.

        Args:
            db: Database session
            organization_id: Organization ID
            flags: List of feature flags to enable

        Returns:
            List of FeatureFlag model instances
        """
        results = []
        for flag in flags:
            result = await self.enable_feature(db, organization_id, flag)
            results.append(result)
        return results


# Create the instance with the updated class name
organization = CRUDOrganization()
