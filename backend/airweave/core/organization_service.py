"""Organization service for managing Auth0 organization synchronization."""

import uuid
from typing import Dict, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas

# Import billing dependencies only if Stripe is enabled
from airweave.core.config import settings
from airweave.core.context import BaseContext
from airweave.core.context_cache_service import context_cache
from airweave.core.logging import logger
from airweave.core.protocols.payment import PaymentGatewayProtocol
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.billing.operations import BillingOperations
from airweave.domains.billing.repository import (
    BillingPeriodRepository,
    OrganizationBillingRepository,
)
from airweave.domains.usage.repository import UsageRepository
from airweave.integrations.auth0_management import auth0_management_client
from airweave.models import Organization, User, UserOrganization
from airweave.schemas.api_key import APIKeyCreate

_billing_repo = OrganizationBillingRepository()
_period_repo = BillingPeriodRepository()
_usage_repo = UsageRepository()

# TODO: Remove this once we have refctored the org service to use DI
if settings.STRIPE_ENABLED:
    from airweave.adapters.payment.stripe import StripePaymentGateway

    _payment_gateway: PaymentGatewayProtocol = StripePaymentGateway()
    _billing_ops = BillingOperations(
        payment_gateway=_payment_gateway,
        billing_repo=_billing_repo,
        period_repo=_period_repo,
        usage_repo=_usage_repo,
    )
else:
    from airweave.adapters.payment.null import NullPaymentGateway

    _payment_gateway: PaymentGatewayProtocol = NullPaymentGateway()
    _billing_ops = BillingOperations(
        payment_gateway=_payment_gateway,
        billing_repo=_billing_repo,
        period_repo=_period_repo,
        usage_repo=_usage_repo,
    )


class OrganizationService:
    """Service for organization management and synchronization with Auth0.

    This class is exempt from using the CRUD classes, due to higher degree of
    complexity in managing organization-related operations.
    """

    def _create_org_name(self, org_data: schemas.OrganizationCreate) -> str:
        """Create a unique organization name for Auth0."""
        small_uuid = str(uuid.uuid4())[:8]
        return f"airweave-{org_data.name.lower().replace(' ', '-')}-{small_uuid}"

    async def create_organization_with_integrations(  # noqa: C901
        self, db: AsyncSession, org_data: schemas.OrganizationCreate, owner_user: User
    ) -> schemas.Organization:
        """Create organization with Auth0 and optionally Stripe integration.

        This method ensures atomicity across all external services:
        1. Creates Auth0 organization
        2. Creates Stripe customer
        3. Creates local organization with optional billing

        On any failure, all changes are rolled back.

        Args:
            db: Database session
            org_data: Organization creation data
            owner_user: User who will own the organization

        Returns:
            Created organization

        Raises:
            Exception: If any step fails, all changes are rolled back
        """
        auth0_org_data = None
        auth0_org_id = None
        stripe_customer = None

        # Determine whether to use Auth0 in this environment
        use_auth0 = bool(settings.AUTH_ENABLED and auth0_management_client)

        try:
            # Step 1: Create Auth0 organization (only when enabled and configured)
            if use_auth0:
                logger.info(f"Creating Auth0 organization for: {org_data.name}")
                auth0_org_data = await auth0_management_client.create_organization(
                    name=self._create_org_name(org_data),
                    display_name=org_data.name,
                )
                auth0_org_id = auth0_org_data["id"]

                # Add user to Auth0 organization as owner
                await auth0_management_client.add_user_to_organization(
                    auth0_org_id, owner_user.auth0_id
                )

                # Enable default connections for the new organization
                await self._setup_auth0_connections(auth0_org_id)

                logger.info(f"Successfully created Auth0 organization: {auth0_org_id}")
            else:
                logger.info(
                    "AUTH disabled or Auth0 client not configured; skipping Auth0 org creation"
                )

            # Step 2: Create payment provider customer (no-op when billing disabled)
            # Test clock support only via environment variable in non-production
            # SECURITY: Never accept test_clock from user input to prevent billing manipulation
            test_clock_id = None
            if settings.ENVIRONMENT != "prd":
                test_clock_id = settings.STRIPE_TEST_CLOCK  # From env only, not user input

            stripe_customer = await _payment_gateway.create_customer(
                email=owner_user.email,
                name=org_data.name,
                metadata={
                    "auth0_org_id": auth0_org_id or "",
                    "owner_user_id": str(owner_user.id),
                    "organization_name": org_data.name,
                },
                test_clock=test_clock_id,
            )
            if stripe_customer:
                logger.info(f"Created Stripe customer: {stripe_customer.id}")

            # Step 3: Create local organization
            async with UnitOfWork(db) as uow:
                # Prepare organization data
                org_dict = org_data.model_dump()
                org_dict["auth0_org_id"] = auth0_org_id

                logger.info(f"Creating organization with data: {org_dict}")

                # Create organization using enhanced CRUD method
                local_org = await crud.organization.create_with_owner(
                    db=db,
                    obj_in=schemas.OrganizationCreate(**org_dict),
                    owner_user=owner_user,
                    uow=uow,
                )
                # Capture primitives immediately to avoid lazy loads later
                org_id = local_org.id

                logger.info(
                    f"Created organization with auth0_org_id: {org_dict.get('auth0_org_id')}"
                )

                # Create billing record if payment provider returned a customer
                if stripe_customer:
                    local_org_schema = schemas.Organization.model_validate(local_org)

                    ctx = BaseContext(organization=local_org_schema)

                    # Create billing record
                    _ = await _billing_ops.create_billing_record(
                        db=db,
                        organization=local_org_schema,
                        stripe_customer_id=stripe_customer.id,
                        billing_email=owner_user.email,
                        ctx=ctx,
                        uow=uow,
                    )

                # Create organization schema response without triggering lazy ORM loads.
                # Fetch concrete columns explicitly and build the Pydantic model from primitives.

                row_result = await db.execute(
                    select(
                        Organization.id,
                        Organization.name,
                        Organization.description,
                        Organization.auth0_org_id,
                        Organization.created_at,
                        Organization.modified_at,
                        Organization.org_metadata,
                    ).where(Organization.id == org_id)
                )
                (
                    org_id,
                    org_name,
                    org_description,
                    org_auth0_id,
                    org_created_at,
                    org_modified_at,
                    org_metadata,
                ) = row_result.one()

                organization = schemas.Organization(
                    id=org_id,
                    name=org_name,
                    description=org_description,
                    auth0_org_id=org_auth0_id,
                    created_at=org_created_at,
                    modified_at=org_modified_at,
                    org_metadata=org_metadata,
                    role="owner",
                )

                # Create API key for the organization
                logger.info(f"Creating API key for organization {org_id}")

                api_key_auth = BaseContext(
                    organization=organization,
                )

                # Create API key with default expiration (180 days)
                api_key_create = APIKeyCreate()
                await crud.api_key.create(
                    db=db,
                    obj_in=api_key_create,
                    ctx=api_key_auth,
                    uow=uow,
                )

                logger.info(f"Successfully created API key for organization {org_id}")

                # Commit the transaction
                await uow.commit()
                logger.info("Successfully created local organization.")

                # Invalidate user cache so subsequent requests see the new organization
                # membership. Without this, the cached user_organizations list won't
                # include the newly created organization, causing 403 errors.
                await context_cache.invalidate_user(owner_user.email)
                logger.debug(f"Invalidated user cache for {owner_user.email}")

                # Svix organization is created lazily on first webhook use
                # (via _auto_create_org in SvixAdapter), no explicit call needed.

                return organization

        except Exception as e:
            # Rollback everything on failure
            logger.error(f"Failed to create organization: {e}")

            # Cleanup Auth0
            if auth0_org_data:
                try:
                    await auth0_management_client.delete_organization(auth0_org_id)
                    logger.info(f"Rolled back Auth0 organization: {auth0_org_id}")
                except Exception as cleanup_error:
                    logger.error(f"Failed to cleanup Auth0 organization: {cleanup_error}")

            # Cleanup payment provider customer if one was created
            if stripe_customer:
                try:
                    await _payment_gateway.delete_customer(stripe_customer.id)
                    logger.info(f"Rolled back Stripe customer: {stripe_customer.id}")
                except Exception as cleanup_error:
                    logger.error(f"Failed to cleanup Stripe customer: {cleanup_error}")

            raise

    async def _setup_auth0_connections(self, auth0_org_id: str) -> None:
        """Setup default Auth0 connections for organization."""
        default_connection_names = [
            "Username-Password-Authentication",
            "google-oauth2",
            "github",
        ]

        all_connections = await auth0_management_client.get_all_connections()
        connections_to_enable = [
            conn["id"] for conn in all_connections if conn["name"] in default_connection_names
        ]

        for conn_id in connections_to_enable:
            await auth0_management_client.add_enabled_connection_to_organization(
                auth0_org_id, conn_id
            )
            logger.info(f"Enabled connection {conn_id} for organization {auth0_org_id}")

    async def handle_new_user_signup(
        self, db: AsyncSession, user_data: Dict, create_org: bool = False
    ) -> User:
        """Handle new user signup - check for Auth0 orgs or create new one.

        Args:
            db: Database session
            user_data: User data from signup
            create_org: Whether to create an organization if none exists (defaults to False)

        Returns:
            Created user
        """
        auth0_id = user_data.get("auth0_id")

        if not auth0_id:
            # No Auth0 ID or Auth0 not enabled
            raise ValueError("No Auth0 ID provided")

        try:
            # Check if user has existing Auth0 organizations
            auth0_orgs = await auth0_management_client.get_user_organizations(auth0_id)

            if auth0_orgs:
                # User has Auth0 organizations, sync them
                logger.info(
                    f"User {user_data.get('email')} has {len(auth0_orgs)} Auth0 organizations"
                )
                return await self._create_user_with_existing_orgs(db, user_data, auth0_orgs)
            else:
                # No Auth0 orgs
                if create_org:
                    logger.info(
                        f"User {user_data.get('email')} has no Auth0 organizations. "
                        "Creating new org."
                    )
                    return await self._create_user_with_new_org(db, user_data)
                else:
                    logger.info(
                        f"User {user_data.get('email')} has no Auth0 organizations. "
                        "Creating user without org."
                    )
                    return await self._create_user_without_org(db, user_data)

        except Exception as e:
            logger.error(f"Failed to check Auth0 organizations for new user: {e}")
            # Fallback behavior
            if create_org:
                return await self._create_user_with_new_org(db, user_data)
            else:
                return await self._create_user_without_org(db, user_data)

    async def sync_user_organizations(self, db: AsyncSession, user: User) -> User:
        """Sync user's Auth0 organizations with local database.

        Args:
            db: Database session
            user: User to sync organizations for

        Returns:
            Updated user with synced organizations
        """
        try:
            # Get user's Auth0 organizations
            auth0_orgs = await auth0_management_client.get_user_organizations(user.auth0_id)

            if not auth0_orgs:
                logger.info(f"User {user.email} has no Auth0 organizations")
                return user

            logger.info(f"Syncing {len(auth0_orgs)} Auth0 organizations for user {user.email}")

            # Sync each organization
            for auth0_org in auth0_orgs:
                await self._sync_single_organization(db, user, auth0_org)

            await db.commit()
            await db.refresh(user)

            logger.info(f"Successfully synced organizations for user {user.email}")
            return user

        except Exception as e:
            logger.error(f"Failed to sync Auth0 organizations for user {user.email}: {e}")
            await db.rollback()
            return user

    # Private helper methods
    async def _sync_single_organization(
        self, db: AsyncSession, user: User, auth0_org: Dict
    ) -> None:
        """Sync a single Auth0 organization to local database."""
        # Check if local organization exists by Auth0 ID
        query = select(Organization).where(Organization.auth0_org_id == auth0_org["id"])
        result = await db.execute(query)
        local_org = result.scalar_one_or_none()

        if not local_org:
            # Create local organization
            local_org = Organization(
                name=auth0_org.get("display_name", auth0_org["name"]),
                description=f"Imported from Auth0: {auth0_org['name']}",
                auth0_org_id=auth0_org["id"],
            )
            db.add(local_org)
            await db.flush()
            logger.info(f"Created local organization for Auth0 org: {auth0_org['id']}")

        # Check if user-organization relationship exists
        query = select(UserOrganization).where(
            UserOrganization.user_id == user.id, UserOrganization.organization_id == local_org.id
        )
        result = await db.execute(query)
        existing_relationship = result.scalar_one_or_none()

        if not existing_relationship:
            # Determine if this should be primary (first org for user)
            query = select(UserOrganization).where(UserOrganization.user_id == user.id)
            result = await db.execute(query)
            user_org_count = len(result.scalars().all())
            is_primary = user_org_count == 0

            # Get user's role from Auth0
            member_roles = await auth0_management_client.get_organization_member_roles(
                org_id=auth0_org["id"], user_id=user.auth0_id
            )

            user_role = "member"  # Default role
            if member_roles:
                # Prioritize 'admin' role if present, otherwise take the first role name
                role_names = [role.get("name") for role in member_roles if role.get("name")]
                if "admin" in role_names:
                    user_role = "admin"
                elif role_names:
                    user_role = role_names[0]

            # Create user-organization relationship
            user_org = UserOrganization(
                user_id=user.id,
                organization_id=local_org.id,
                role=user_role,
                is_primary=is_primary,
            )
            db.add(user_org)
            logger.info(
                f"Created user-organization relationship for user {user.id} and "
                f"org {local_org.id} with role {user_role}"
            )

    async def _create_user_with_new_org(self, db: AsyncSession, user_data: Dict) -> User:
        """Create user with a new organization."""
        try:
            # Use the existing CRUD method that creates user with organization
            user_create = schemas.UserCreate(**user_data)
            user, org = await crud.user.create_with_organization(db, obj_in=user_create)

            logger.info(f"Created user {user.email} with new organization {org.name}")
            return user

        except Exception as e:
            logger.error(f"Failed to create user with new organization: {e}")
            raise

    async def _create_user_with_existing_orgs(
        self, db: AsyncSession, user_data: Dict, auth0_orgs: List[Dict]
    ) -> User:
        """Create user and sync with existing Auth0 organizations."""
        async with UnitOfWork(db) as uow:
            try:
                # Create user first without organization
                user_create = schemas.UserCreate(**user_data)
                user = User(**user_create.model_dump())
                db.add(user)
                await db.flush()  # Get the user ID

                # Sync organizations
                for auth0_org in auth0_orgs:
                    await self._sync_single_organization(db, user, auth0_org)

                await uow.commit()
                await db.refresh(user)

                logger.info(f"Created user {user.email} and synced {len(auth0_orgs)} organizations")
                return user

            except Exception as e:
                await uow.rollback()
                logger.error(f"Failed to create user with existing organizations: {e}")
                raise

    async def _create_user_without_org(self, db: AsyncSession, user_data: Dict) -> User:
        """Create user without an organization."""
        try:
            # Use the existing CRUD method that creates user without organization
            user_create = schemas.UserCreate(**user_data)
            user = User(**user_create.model_dump())
            db.add(user)
            await db.flush()  # Get the user ID
            await db.commit()  # Commit the transaction
            await db.refresh(user)  # Refresh to get the latest state

            logger.info(f"Created user {user.email} without an organization")
            return user

        except Exception as e:
            logger.error(f"Failed to create user without an organization: {e}")
            raise

    # Member Management Methods
    async def invite_user_to_organization(
        self,
        db: AsyncSession,
        organization_id: UUID,
        email: str,
        role: str,
        inviter_user: schemas.User,
    ) -> Dict:
        """Send organization invitation via Auth0."""
        from sqlalchemy import select

        # Get organization with Auth0 ID
        query = select(Organization).where(Organization.id == organization_id)
        result = await db.execute(query)
        org = result.scalar_one_or_none()

        if not org:
            raise ValueError("Organization not found")

        # Send Auth0 invitation
        invitation = await auth0_management_client.invite_user_to_organization(
            org.auth0_org_id, email, role, inviter_user
        )
        logger.info(f"Successfully sent Auth0 invitation to {email} for organization {org.name}")
        return invitation

    async def _delete_from_auth0(self, org: Organization) -> None:
        """Delete organization from Auth0.

        Args:
            org: Organization to delete from Auth0

        Note:
            Continues execution even if Auth0 deletion fails to prevent partial deletion states.
        """
        if org.auth0_org_id and auth0_management_client:
            try:
                await auth0_management_client.delete_organization(org.auth0_org_id)
                logger.info(f"Successfully deleted Auth0 organization: {org.auth0_org_id}")
            except Exception as e:
                logger.warning(f"Failed to delete Auth0 organization {org.auth0_org_id}: {e}")

    async def _delete_billing_subscription(
        self, db: AsyncSession, organization_id: UUID, org_name: str
    ) -> None:
        """Delete billing subscription for organization.

        Args:
            db: Database session
            organization_id: ID of the organization
            org_name: Name of the organization (for logging)

        Note:
            Continues execution even if billing deletion fails.
        """
        try:
            org_billing = await crud.organization_billing.get_by_organization(
                db, organization_id=organization_id
            )
            if not org_billing:
                logger.warning(f"No billing record found for organization {org_name}")
            else:
                await _payment_gateway.cancel_subscription(
                    subscription_id=org_billing.stripe_subscription_id,
                    at_period_end=False,
                )
            logger.info(f"Successfully deleted billing record for organization: {org_name}")
        except Exception as e:
            logger.warning(f"Failed to delete billing record for organization {org_name}: {e}")

    async def _delete_user_organization_relationships(
        self, db: AsyncSession, organization_id: UUID, org_name: str
    ) -> List[str]:
        """Delete all user-organization relationships.

        Args:
            db: Database session
            organization_id: ID of the organization
            org_name: Name of the organization (for logging)

        Returns:
            List of user emails whose memberships were deleted (for cache invalidation
            after transaction commit)
        """
        from sqlalchemy import delete, select

        # First, get all users in this organization so we can invalidate their cache
        user_query = (
            select(User.email)
            .join(UserOrganization, User.id == UserOrganization.user_id)
            .where(UserOrganization.organization_id == organization_id)
        )
        result = await db.execute(user_query)
        user_emails = [row[0] for row in result.fetchall()]

        # Delete the relationships
        delete_user_org_stmt = delete(UserOrganization).where(
            UserOrganization.organization_id == organization_id
        )
        await db.execute(delete_user_org_stmt)
        logger.info(f"Deleted user-organization relationships for organization {org_name}")

        # Return emails for cache invalidation after commit
        return user_emails

    async def _delete_organization_from_db(
        self, db: AsyncSession, organization_id: UUID, org_name: str
    ) -> None:
        """Delete organization from local database.

        Args:
            db: Database session
            organization_id: ID of the organization
            org_name: Name of the organization (for logging)

        Note:
            CASCADE will delete related collections from SQL.
        """
        from sqlalchemy import delete

        delete_org_stmt = delete(Organization).where(Organization.id == organization_id)
        await db.execute(delete_org_stmt)
        await db.commit()
        logger.info(f"Successfully deleted local organization: {org_name}")

    async def delete_organization_with_integrations(
        self, db: AsyncSession, organization_id: UUID, deleting_user: User
    ) -> bool:
        """Delete organization from both local database and Auth0.

        Args:
            db: Database session
            organization_id: ID of the organization to delete
            deleting_user: User performing the deletion

        Returns:
            True if deletion was successful

        Raises:
            Exception: If deletion fails
        """
        from sqlalchemy import select

        # Get organization with Auth0 ID
        query = select(Organization).where(Organization.id == organization_id)
        result = await db.execute(query)
        org = result.scalar_one_or_none()

        if not org:
            raise ValueError("Organization not found")

        logger.info(f"Starting deletion of organization {org.name} (ID: {organization_id})")

        try:
            # Delete from Auth0 first if it has an Auth0 org ID
            await self._delete_from_auth0(org)

            # Delete billing subscription if Stripe is enabled
            await self._delete_billing_subscription(db, organization_id, org.name)

            # Delete user-organization relationships (returns emails for cache invalidation)
            affected_user_emails = await self._delete_user_organization_relationships(
                db, organization_id, org.name
            )

            # Delete the organization from database (CASCADE will delete collections from SQL)
            # This commits the transaction
            await self._delete_organization_from_db(db, organization_id, org.name)

            # Invalidate user caches AFTER the transaction is committed
            # This prevents race conditions where another request could repopulate
            # the cache with stale data before the commit
            for email in affected_user_emails:
                await context_cache.invalidate_user(email)
            if affected_user_emails:
                logger.debug(f"Invalidated user cache for {len(affected_user_emails)} users")

            # Delete organization from webhooks (Svix application cleanup)
            # TODO: delete this after DI is implemented for OrganizationService
            from airweave.core.container import container

            if container is not None:
                await container.webhook_admin.delete_organization(org.id)

            logger.info(f"Successfully deleted organization: {org.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete organization {org.name}: {e}")
            # If we deleted from Auth0 but failed locally, log this as a critical issue
            if org.auth0_org_id:
                logger.critical(
                    f"Organization {org.name} was deleted from Auth0 but failed to delete locally. "
                    f"Auth0 org ID: {org.auth0_org_id}, Local org ID: {organization_id}"
                )
            raise

    async def remove_pending_invitation(
        self, db: AsyncSession, organization_id: UUID, invitation_id: str, remover_user: User
    ) -> bool:
        """Remove a pending invitation."""
        from sqlalchemy import select

        # Get organization with Auth0 ID
        query = select(Organization).where(Organization.id == organization_id)
        result = await db.execute(query)
        org = result.scalar_one_or_none()

        if not org:
            raise ValueError("Organization not found")

        await auth0_management_client.delete_invitation(org.auth0_org_id, invitation_id)
        logger.info(f"Successfully removed invitation {invitation_id} from organization {org.name}")
        return True

    async def remove_member_from_organization(
        self, db: AsyncSession, organization_id: UUID, user_id: UUID, remover_user: User
    ) -> bool:
        """Remove a member from organization (both local and Auth0)."""
        from sqlalchemy import delete, select

        # Get the user to be removed
        user_query = select(User).where(User.id == user_id)
        user_result = await db.execute(user_query)
        user_to_remove = user_result.scalar_one_or_none()

        if not user_to_remove:
            raise ValueError("User not found")

        # Get organization
        org_query = select(Organization).where(Organization.id == organization_id)
        org_result = await db.execute(org_query)
        org = org_result.scalar_one_or_none()

        if not org:
            raise ValueError("Organization not found")

        # Capture values before async operations to avoid greenlet errors

        user_schema = schemas.User.model_validate(user_to_remove)
        org_schema = schemas.Organization.model_validate(org)

        await auth0_management_client.remove_user_from_organization(
            org_schema.auth0_org_id, user_schema.auth0_id
        )
        logger.info(f"Removed user {user_schema.email} from Auth0 organization {org_schema.name}")

        # Remove from local database
        delete_stmt = delete(UserOrganization).where(
            UserOrganization.user_id == user_id,
            UserOrganization.organization_id == organization_id,
        )
        await db.execute(delete_stmt)
        await db.commit()

        # Invalidate user cache so subsequent requests reflect the membership change
        await context_cache.invalidate_user(user_schema.email)
        logger.debug(f"Invalidated user cache for {user_schema.email}")

        logger.info(
            f"Successfully removed user {user_schema.email} from organization {org_schema.name}"
        )
        return True

    async def handle_user_leaving_organization(
        self, db: AsyncSession, organization_id: UUID, leaving_user: User
    ) -> bool:
        """Handle user leaving an organization."""
        # Use the existing remove_member_from_organization method
        # but with the user removing themselves
        return await self.remove_member_from_organization(
            db, organization_id, leaving_user.id, leaving_user
        )

    async def get_organization_members(
        self, db: AsyncSession, organization_id: UUID, requesting_user: User
    ) -> List[Dict]:
        """Get all members of an organization."""
        from sqlalchemy import select

        # Get organization
        org_query = select(Organization).where(Organization.id == organization_id)
        org_result = await db.execute(org_query)
        org = org_result.scalar_one_or_none()

        if not org:
            raise ValueError("Organization not found")

        # Get local members
        members_query = (
            select(User, UserOrganization.role, UserOrganization.is_primary)
            .join(UserOrganization, User.id == UserOrganization.user_id)
            .where(UserOrganization.organization_id == organization_id)
        )
        members_result = await db.execute(members_query)
        local_members = members_result.all()

        # Format members
        members = []
        for user, role, is_primary in local_members:
            members.append(
                {
                    "id": str(user.id),
                    "email": user.email,
                    "name": user.full_name or user.email,
                    "role": role,
                    "status": "active",
                    "is_primary": is_primary,
                    "auth0_id": user.auth0_id,
                }
            )

        return members

    async def get_pending_invitations(
        self, db: AsyncSession, organization_id: UUID, requesting_user: User
    ) -> List[Dict]:
        """Get pending invitations for an organization."""
        from sqlalchemy import select

        # Get organization
        org_query = select(Organization).where(Organization.id == organization_id)
        org_result = await db.execute(org_query)
        org = org_result.scalar_one_or_none()

        if not org:
            raise ValueError("Organization not found")

        # Get all roles from Auth0 to create role ID -> role name mapping
        all_roles = await auth0_management_client.get_roles()
        role_id_to_name = {role["id"]: role["name"] for role in all_roles}

        auth0_invitations = await auth0_management_client.get_pending_invitations(org.auth0_org_id)

        # Format invitations
        invitations = []
        for invitation in auth0_invitations:
            # Extract role from the roles array (Auth0 stores role IDs in roles array)
            role_ids = invitation.get("roles", [])
            role_name = "member"  # Default role
            if role_ids:
                # Take the first role ID and map it to role name
                first_role_id = role_ids[0]
                role_name = role_id_to_name.get(first_role_id, "member")

            invitations.append(
                {
                    "id": invitation.get("id"),
                    "email": invitation.get("invitee", {}).get("email"),
                    "role": role_name,
                    "invited_at": invitation.get("created_at"),
                    "status": "pending",
                }
            )

        return invitations


organization_service = OrganizationService()
