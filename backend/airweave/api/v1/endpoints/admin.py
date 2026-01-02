"""Admin-only API endpoints for organization management."""

from typing import List, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.router import TrailingSlashRouter
from airweave.billing.service import billing_service
from airweave.core.context_cache_service import context_cache
from airweave.core.exceptions import InvalidStateError, NotFoundException
from airweave.core.organization_service import organization_service
from airweave.core.shared_models import FeatureFlag as FeatureFlagEnum
from airweave.crud.crud_organization_billing import organization_billing
from airweave.db.unit_of_work import UnitOfWork
from airweave.integrations.auth0_management import auth0_management_client
from airweave.integrations.stripe_client import stripe_client
from airweave.models.collection import Collection
from airweave.models.connection import Connection
from airweave.models.organization import Organization
from airweave.models.organization_billing import OrganizationBilling
from airweave.models.source_connection import SourceConnection
from airweave.models.sync import Sync
from airweave.models.sync_connection import SyncConnection
from airweave.models.user_organization import UserOrganization
from airweave.schemas.organization_billing import BillingPlan, BillingStatus

router = TrailingSlashRouter()


@router.get("/feature-flags", response_model=List[dict])
async def list_available_feature_flags(
    ctx: ApiContext = Depends(deps.get_context),
) -> List[dict]:
    """Get all available feature flags in the system (admin only).

    Args:
        ctx: API context

    Returns:
        List of feature flag definitions with name and value

    Raises:
        HTTPException: If user is not an admin
    """
    _require_admin(ctx)

    # Return all feature flags from the enum
    return [{"name": flag.name, "value": flag.value} for flag in FeatureFlagEnum]


def _require_admin(ctx: ApiContext) -> None:
    """Validate that the user is an admin or superuser.

    Args:
        ctx: The API context

    Raises:
        HTTPException: If user is not an admin or superuser
    """
    from airweave.core.config import settings

    # Allow local admin access when enabled (for development)
    if settings.LOCAL_ADMIN_ACCESS and settings.ENVIRONMENT == "local":
        return

    # Allow both explicit admins AND superusers (for system operations and tests)
    if not ctx.has_user_context or not (ctx.user.is_admin or ctx.user.is_superuser):
        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/organizations", response_model=List[schemas.OrganizationMetrics])
async def list_all_organizations(
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    skip: int = 0,
    limit: int = Query(1000, le=10000, description="Maximum number of organizations to return"),
    search: Optional[str] = Query(None, description="Search by organization name"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", description="Sort order (asc or desc)"),
) -> List[schemas.OrganizationMetrics]:
    """List all organizations with comprehensive metrics (admin only).

    This endpoint fetches all organizations with their billing info and usage metrics
    using optimized queries to minimize database round-trips.

    Args:
        db: Database session
        ctx: API context
        skip: Number of organizations to skip
        limit: Maximum number of organizations to return (default 1000, max 10000)
        search: Optional search term to filter by organization name
        sort_by: Field to sort by (name, created_at, billing_plan, user_count,
            source_connection_count, entity_count, query_count, last_active_at)
        sort_order: Sort order (asc or desc)

    Returns:
        List of all organizations with comprehensive metrics

    Raises:
        HTTPException: If user is not an admin
    """
    _require_admin(ctx)

    # Import for joins
    from datetime import datetime

    from airweave.models.billing_period import BillingPeriod
    from airweave.models.usage import Usage
    from airweave.models.user import User
    from airweave.schemas.billing_period import BillingPeriodStatus

    # Build the base query with billing join
    query = select(Organization).outerjoin(
        OrganizationBilling, Organization.id == OrganizationBilling.organization_id
    )

    # For usage-based sorting, we need to join Usage and BillingPeriod
    # Only add these joins if sorting by usage fields
    usage_sort_fields = ["entity_count", "query_count"]
    if sort_by in usage_sort_fields:
        now = datetime.utcnow()
        query = query.outerjoin(
            BillingPeriod,
            and_(
                BillingPeriod.organization_id == Organization.id,
                BillingPeriod.period_start <= now,
                BillingPeriod.period_end > now,
                BillingPeriod.status.in_(
                    [
                        BillingPeriodStatus.ACTIVE,
                        BillingPeriodStatus.TRIAL,
                        BillingPeriodStatus.GRACE,
                    ]
                ),
            ),
        ).outerjoin(Usage, Usage.billing_period_id == BillingPeriod.id)

    # For user_count sorting, create subquery
    if sort_by == "user_count":
        from sqlalchemy import select as sa_select

        user_count_subq = (
            sa_select(
                UserOrganization.organization_id,
                func.count(UserOrganization.user_id).label("user_count"),
            )
            .group_by(UserOrganization.organization_id)
            .subquery()
        )

        query = query.outerjoin(
            user_count_subq, Organization.id == user_count_subq.c.organization_id
        )

    # For source_connection_count sorting, create subquery
    if sort_by == "source_connection_count":
        from sqlalchemy import select as sa_select

        from airweave.models.source_connection import SourceConnection

        source_connection_count_subq = (
            sa_select(
                SourceConnection.organization_id,
                func.count(SourceConnection.id).label("source_connection_count"),
            )
            .group_by(SourceConnection.organization_id)
            .subquery()
        )

        query = query.outerjoin(
            source_connection_count_subq,
            Organization.id == source_connection_count_subq.c.organization_id,
        )

    # For last_active_at sorting, join with User through UserOrganization
    if sort_by == "last_active_at":
        # Subquery to get max last_active_at per organization
        from sqlalchemy import select as sa_select

        max_active_subq = (
            sa_select(
                UserOrganization.organization_id,
                func.max(User.last_active_at).label("max_last_active"),
            )
            .join(User, UserOrganization.user_id == User.id)
            .group_by(UserOrganization.organization_id)
            .subquery()
        )

        query = query.outerjoin(
            max_active_subq, Organization.id == max_active_subq.c.organization_id
        )

    # Apply search filter
    if search:
        query = query.where(Organization.name.ilike(f"%{search}%"))

    # Apply sorting - handle special cases for joined fields
    # Note: is_member sorting is handled client-side since it requires admin user context
    sort_column = None
    if sort_by == "billing_plan":
        sort_column = OrganizationBilling.billing_plan
    elif sort_by == "billing_status":
        sort_column = OrganizationBilling.billing_status
    elif sort_by == "entity_count":
        sort_column = Usage.entities
    elif sort_by == "query_count":
        sort_column = Usage.queries
    elif sort_by == "user_count":
        sort_column = user_count_subq.c.user_count
    elif sort_by == "source_connection_count":
        sort_column = source_connection_count_subq.c.source_connection_count
    elif sort_by == "last_active_at":
        sort_column = max_active_subq.c.max_last_active
    elif sort_by == "is_member":
        # This will be handled client-side, use created_at as default
        sort_column = Organization.created_at
    elif hasattr(Organization, sort_by):
        sort_column = getattr(Organization, sort_by)
    else:
        # Default to created_at if invalid field
        sort_column = Organization.created_at

    if sort_order.lower() == "asc":
        query = query.order_by(sort_column.asc().nullslast())
    else:
        query = query.order_by(sort_column.desc().nullslast())

    # Apply pagination
    query = query.offset(skip).limit(limit)

    # Execute query
    result = await db.execute(query)
    orgs = list(result.scalars().all())

    if not orgs:
        return []

    org_ids = [org.id for org in orgs]

    # Fetch all billing info in one query
    billing_query = select(OrganizationBilling).where(
        OrganizationBilling.organization_id.in_(org_ids)
    )
    billing_result = await db.execute(billing_query)
    billing_map = {b.organization_id: b for b in billing_result.scalars().all()}

    # Fetch user counts in one query
    user_count_query = (
        select(
            UserOrganization.organization_id,
            func.count(UserOrganization.user_id).label("count"),
        )
        .where(UserOrganization.organization_id.in_(org_ids))
        .group_by(UserOrganization.organization_id)
    )
    user_count_result = await db.execute(user_count_query)
    user_count_map = {row.organization_id: row.count for row in user_count_result}

    # Fetch admin's memberships in these organizations
    admin_membership_query = select(UserOrganization).where(
        UserOrganization.user_id == ctx.user.id,
        UserOrganization.organization_id.in_(org_ids),
    )
    admin_membership_result = await db.execute(admin_membership_query)
    admin_membership_map = {
        uo.organization_id: uo.role for uo in admin_membership_result.scalars().all()
    }

    # Fetch last active timestamp for each organization (most recent user activity)
    from airweave.models.user import User

    last_active_query = (
        select(
            UserOrganization.organization_id,
            func.max(User.last_active_at).label("last_active"),
        )
        .join(User, UserOrganization.user_id == User.id)
        .where(UserOrganization.organization_id.in_(org_ids))
        .group_by(UserOrganization.organization_id)
    )
    last_active_result = await db.execute(last_active_query)
    last_active_map = {row.organization_id: row.last_active for row in last_active_result}

    # Fetch current usage for all organizations using CRUD layer
    usage_map = await crud.usage.get_current_usage_for_orgs(db, organization_ids=org_ids)

    # Fetch source connection counts in one query (dynamically counted, not stored in usage)
    from airweave.models.source_connection import SourceConnection

    source_connection_count_query = (
        select(
            SourceConnection.organization_id,
            func.count(SourceConnection.id).label("count"),
        )
        .where(SourceConnection.organization_id.in_(org_ids))
        .group_by(SourceConnection.organization_id)
    )
    source_connection_result = await db.execute(source_connection_count_query)
    source_connection_map = {row.organization_id: row.count for row in source_connection_result}

    # Build response with all metrics
    org_metrics = []
    for org in orgs:
        billing = billing_map.get(org.id)
        usage_record = usage_map.get(org.id)
        admin_role = admin_membership_map.get(org.id)

        # Extract enabled features from the relationship
        enabled_features = [FeatureFlagEnum(ff.flag) for ff in org.feature_flags if ff.enabled]

        org_metrics.append(
            schemas.OrganizationMetrics(
                id=org.id,
                name=org.name,
                description=org.description,
                created_at=org.created_at,
                modified_at=org.modified_at,
                auth0_org_id=org.auth0_org_id,
                billing_plan=billing.billing_plan if billing else None,
                billing_status=billing.billing_status if billing else None,
                stripe_customer_id=billing.stripe_customer_id if billing else None,
                trial_ends_at=billing.trial_ends_at if billing else None,
                user_count=user_count_map.get(org.id, 0),
                source_connection_count=source_connection_map.get(org.id, 0),
                entity_count=usage_record.entities if usage_record else 0,
                query_count=usage_record.queries if usage_record else 0,
                last_active_at=last_active_map.get(org.id),
                is_member=admin_role is not None,
                member_role=admin_role,
                enabled_features=enabled_features,
            )
        )

    ctx.logger.info(
        f"Admin retrieved {len(org_metrics)} organizations "
        f"(search={search}, sort_by={sort_by}, sort_order={sort_order})"
    )

    return org_metrics


@router.post(
    "/organizations/{organization_id}/add-self",
    response_model=schemas.OrganizationWithRole,
)
async def add_self_to_organization(
    organization_id: UUID,
    role: str = "owner",  # Default to owner for admins
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.OrganizationWithRole:
    """Add the admin user to an organization (admin only).

    This allows admins to join any organization for support purposes.

    Args:
        organization_id: The organization to join
        role: Role to assign (owner, admin, or member)
        db: Database session
        ctx: API context

    Returns:
        The organization with the admin's new role

    Raises:
        HTTPException: If user is not an admin or organization doesn't exist
    """
    _require_admin(ctx)

    # Validate role
    if role not in ["owner", "admin", "member"]:
        raise HTTPException(status_code=400, detail="Invalid role. Must be owner, admin, or member")

    # Check if organization exists
    org = await crud.organization.get(db, organization_id, ctx)
    if not org:
        raise NotFoundException(f"Organization {organization_id} not found")

    # Capture org values before any commits to avoid detached instance issues
    org_data = {
        "id": org.id,
        "name": org.name,
        "description": org.description,
        "created_at": org.created_at,
        "modified_at": org.modified_at,
        "auth0_org_id": org.auth0_org_id,
        "org_metadata": org.org_metadata,
    }

    membership_changed = False

    # Check if user is already a member
    existing_user_org = None
    for user_org in ctx.user.user_organizations:
        if user_org.organization.id == organization_id:
            existing_user_org = user_org
            break

    if existing_user_org:
        # Update role if different
        if existing_user_org.role != role:
            from sqlalchemy import update

            stmt = (
                update(UserOrganization)
                .where(
                    UserOrganization.user_id == ctx.user.id,
                    UserOrganization.organization_id == organization_id,
                )
                .values(role=role)
            )
            await db.execute(stmt)
            await db.commit()
            membership_changed = True
            ctx.logger.info(
                f"Admin {ctx.user.email} updated role in org {organization_id} to {role}"
            )
        else:
            ctx.logger.info(
                f"Admin {ctx.user.email} already member of org {organization_id} with role {role}"
            )
    else:
        # Add user to organization - create UserOrganization relationship directly
        try:
            user_org = UserOrganization(
                user_id=ctx.user.id,
                organization_id=organization_id,
                role=role,
                is_primary=False,
            )
            db.add(user_org)
            await db.commit()
            membership_changed = True
            ctx.logger.info(
                f"Admin {ctx.user.email} added self to org {organization_id} with role {role}"
            )
        except Exception as e:
            ctx.logger.error(f"Failed to add admin to organization: {e}")
            await db.rollback()
            raise HTTPException(
                status_code=500, detail=f"Failed to add user to organization: {str(e)}"
            )

    # Also add to Auth0 if available
    try:
        if org_data["auth0_org_id"] and ctx.user.auth0_id and auth0_management_client:
            await auth0_management_client.add_user_to_organization(
                org_id=org_data["auth0_org_id"],
                user_id=ctx.user.auth0_id,
            )
            ctx.logger.info(f"Added admin {ctx.user.email} to Auth0 org {org_data['auth0_org_id']}")
    except Exception as e:
        ctx.logger.warning(f"Failed to add admin to Auth0 organization: {e}")
        # Don't fail the request if Auth0 fails

    if membership_changed and ctx.user and ctx.user.email:
        await context_cache.invalidate_user(ctx.user.email)

    return schemas.OrganizationWithRole(
        id=org_data["id"],
        name=org_data["name"],
        description=org_data["description"],
        created_at=org_data["created_at"],
        modified_at=org_data["modified_at"],
        role=role,
        is_primary=False,
        auth0_org_id=org_data["auth0_org_id"],
        org_metadata=org_data["org_metadata"],
    )


@router.post("/organizations/{organization_id}/upgrade-to-enterprise")
async def upgrade_organization_to_enterprise(  # noqa: C901
    organization_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.Organization:
    """Upgrade an organization to enterprise plan (admin only).

    Uses the existing billing service infrastructure to properly handle
    enterprise upgrades with Stripe customer and $0 subscription management.

    For new billing: Creates Stripe customer + $0 enterprise subscription
    For existing billing: Upgrades plan using billing service

    Args:
        organization_id: The organization to upgrade
        db: Database session
        ctx: API context

    Returns:
        The updated organization

    Raises:
        HTTPException: If user is not an admin or organization doesn't exist
    """
    _require_admin(ctx)

    # Get organization as ORM model (enrich=False) to allow mutations and db.refresh()
    org = await crud.organization.get(db, organization_id, ctx, enrich=False)
    if not org:
        raise NotFoundException(f"Organization {organization_id} not found")

    org_schema = schemas.Organization.model_validate(org, from_attributes=True)

    # Check if billing record exists
    billing = await organization_billing.get_by_organization(db, organization_id=organization_id)

    if not billing:
        # No billing record - create one using the billing service
        ctx.logger.info(f"Creating enterprise billing for org {organization_id}")

        # Get owner email
        owner_email = ctx.user.email if ctx.user else "admin@airweave.ai"
        stmt = select(UserOrganization).where(
            UserOrganization.organization_id == organization_id,
            UserOrganization.role == "owner",
        )
        result = await db.execute(stmt)
        owner_user_org = result.scalar_one_or_none()

        if owner_user_org:
            from airweave.models.user import User

            stmt = select(User).where(User.id == owner_user_org.user_id)
            result = await db.execute(stmt)
            owner_user = result.scalar_one_or_none()
            if owner_user:
                owner_email = owner_user.email

        # Set enterprise in org metadata for billing service
        if not org.org_metadata:
            org.org_metadata = {}
        org.org_metadata["plan"] = "enterprise"
        await db.flush()

        # Create system context for billing operations
        internal_ctx = billing_service._create_system_context(org_schema, "admin_upgrade")

        # Create Stripe customer
        if not stripe_client:
            raise InvalidStateError("Stripe is not enabled")

        customer = await stripe_client.create_customer(
            email=owner_email,
            name=org.name,
            metadata={
                "organization_id": str(organization_id),
                "plan": "enterprise",
            },
        )

        # Use billing service to create record (handles $0 subscription)
        async with UnitOfWork(db) as uow:
            await billing_service.create_billing_record(
                db=db,
                organization=org,
                stripe_customer_id=customer.id,
                billing_email=owner_email,
                ctx=internal_ctx,
                uow=uow,
                contextual_logger=ctx.logger,
            )
            await uow.commit()

        ctx.logger.info(f"Created enterprise billing for org {organization_id}")
    else:
        # Billing exists - cancel old subscription and create new enterprise one
        # The webhook will handle updating billing record and creating periods
        ctx.logger.info(f"Upgrading org {organization_id} to enterprise")

        # Cancel existing subscription if any
        if billing.stripe_subscription_id:
            try:
                await stripe_client.cancel_subscription(
                    billing.stripe_subscription_id, at_period_end=False
                )
                ctx.logger.info(f"Cancelled subscription {billing.stripe_subscription_id}")
            except Exception as e:
                ctx.logger.warning(f"Failed to cancel subscription: {e}")

        # Create new $0 enterprise subscription
        # Webhook will update billing record with subscription_id, plan, periods, etc.
        if stripe_client:
            price_id = stripe_client.get_price_for_plan(BillingPlan.ENTERPRISE)
            if price_id:
                sub = await stripe_client.create_subscription(
                    customer_id=billing.stripe_customer_id,
                    price_id=price_id,
                    metadata={
                        "organization_id": str(organization_id),
                        "plan": "enterprise",
                    },
                )
                ctx.logger.info(
                    f"Created $0 enterprise subscription {sub.id}, "
                    f"webhook will update billing record"
                )
            else:
                raise InvalidStateError("Enterprise price ID not configured")
        else:
            raise InvalidStateError("Stripe is not enabled")

        await db.commit()
        ctx.logger.info(f"Enterprise subscription created for org {organization_id}")

    # Refresh and return
    await db.refresh(org)
    await context_cache.invalidate_organization(organization_id)
    return schemas.Organization.model_validate(org)


@router.post("/organizations/create-enterprise", response_model=schemas.Organization)
async def create_enterprise_organization(
    organization_data: schemas.OrganizationCreate,
    owner_email: str,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.Organization:
    """Create a new enterprise organization (admin only).

    This creates an organization directly on the enterprise plan.

    Args:
        organization_data: The organization data
        owner_email: Email of the user who will own this organization
        db: Database session
        ctx: API context

    Returns:
        The created organization

    Raises:
        HTTPException: If user is not an admin or owner user doesn't exist
    """
    _require_admin(ctx)

    # Find the owner user
    try:
        owner_user = await crud.user.get_by_email(db, email=owner_email)
    except NotFoundException:
        raise HTTPException(status_code=404, detail=f"User with email {owner_email} not found")

    # Create organization with enterprise billing
    async with UnitOfWork(db) as uow:
        # Create the organization (without Auth0/Stripe integration to avoid automatic trial setup)
        from airweave.core.datetime_utils import utc_now_naive
        from airweave.models.organization import Organization
        from airweave.models.organization_billing import OrganizationBilling

        org = Organization(
            name=organization_data.name,
            description=organization_data.description,
            created_by_email=ctx.user.email,
            modified_by_email=ctx.user.email,
        )
        uow.session.add(org)
        await uow.session.flush()

        # Add owner to organization
        user_org = UserOrganization(
            user_id=owner_user.id,
            organization_id=org.id,
            role="owner",
            is_primary=len(owner_user.user_organizations) == 0,  # Primary if first org
        )
        uow.session.add(user_org)

        # Create Stripe customer
        try:
            customer = await stripe_client.create_customer(
                email=owner_email,
                name=org.name,
                metadata={"organization_id": str(org.id), "plan": "enterprise"},
            )

            # Create enterprise billing record
            billing = OrganizationBilling(
                organization_id=org.id,
                stripe_customer_id=customer.id,
                stripe_subscription_id=None,
                billing_plan="enterprise",
                billing_status=BillingStatus.ACTIVE,
                billing_email=owner_email,
                payment_method_added=True,
                current_period_start=utc_now_naive(),
                current_period_end=None,
            )
            uow.session.add(billing)
        except Exception as e:
            ctx.logger.error(f"Failed to create Stripe customer for enterprise org: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create billing: {str(e)}")

        await uow.session.commit()
        await uow.session.refresh(org)

        ctx.logger.info(f"Created enterprise organization {org.id} for {owner_email}")

    # Try to create Auth0 organization (best effort)
    try:
        if owner_user.auth0_id and auth0_management_client:
            # Create Auth0 org name (lowercase, URL-safe)
            auth0_org_name = organization_service._create_org_name(
                schemas.OrganizationCreate(name=org.name, description=org.description)
            )

            auth0_org = await auth0_management_client.create_organization(
                name=auth0_org_name,
                display_name=org.name,
            )

            # Update org with Auth0 ID
            org.auth0_org_id = auth0_org["id"]
            await db.commit()
            await db.refresh(org)

            # Add owner to Auth0 org
            await auth0_management_client.add_user_to_organization(
                org_id=auth0_org["id"],
                user_id=owner_user.auth0_id,
            )

            ctx.logger.info(f"Created Auth0 organization for {org.id}")
    except Exception as e:
        ctx.logger.warning(f"Failed to create Auth0 organization: {e}")
        # Don't fail the request if Auth0 fails

    await context_cache.invalidate_user(owner_user.email)

    return schemas.Organization.model_validate(org)


@router.post("/organizations/{organization_id}/feature-flags/{flag}/enable")
async def enable_feature_flag(
    organization_id: UUID,
    flag: str,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> dict:
    """Enable a feature flag for an organization (admin only).

    Args:
        organization_id: The organization ID
        flag: The feature flag name to enable
        db: Database session
        ctx: API context

    Returns:
        Success message with flag details

    Raises:
        HTTPException: If user is not an admin, organization doesn't exist, or invalid flag
    """
    _require_admin(ctx)

    # Verify organization exists
    org = await crud.organization.get(db, organization_id, ctx, skip_access_validation=True)
    if not org:
        raise NotFoundException(f"Organization {organization_id} not found")

    # Validate flag exists
    try:
        feature_flag = FeatureFlagEnum(flag)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid feature flag: {flag}")

    # Enable the feature
    await crud.organization.enable_feature(db, organization_id, feature_flag)

    # Invalidate organization cache so next request sees updated feature flags
    await context_cache.invalidate_organization(organization_id)

    ctx.logger.info(f"Admin enabled feature flag {flag} for org {organization_id}")

    return {"message": f"Feature flag '{flag}' enabled", "organization_id": str(organization_id)}


@router.post("/organizations/{organization_id}/feature-flags/{flag}/disable")
async def disable_feature_flag(
    organization_id: UUID,
    flag: str,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> dict:
    """Disable a feature flag for an organization (admin only).

    Args:
        organization_id: The organization ID
        flag: The feature flag name to disable
        db: Database session
        ctx: API context

    Returns:
        Success message with flag details

    Raises:
        HTTPException: If user is not an admin, organization doesn't exist, or invalid flag
    """
    _require_admin(ctx)

    # Verify organization exists
    org = await crud.organization.get(db, organization_id, ctx, skip_access_validation=True)
    if not org:
        raise NotFoundException(f"Organization {organization_id} not found")

    # Validate flag exists
    try:
        feature_flag = FeatureFlagEnum(flag)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid feature flag: {flag}")

    # Disable the feature
    await crud.organization.disable_feature(db, organization_id, feature_flag)

    # Invalidate organization cache so next request sees updated feature flags
    await context_cache.invalidate_organization(organization_id)

    ctx.logger.info(f"Admin disabled feature flag {flag} for org {organization_id}")

    return {"message": f"Feature flag '{flag}' disabled", "organization_id": str(organization_id)}


@router.get("/syncs", response_model=List[dict])
async def list_all_syncs_for_migration(
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    organization_id: Optional[UUID] = Query(None, description="Filter by organization"),
    search: Optional[str] = Query(None, description="Search by collection name"),
    limit: int = Query(500, le=1000),
) -> List[dict]:
    """List all syncs with collection and destination info for migration dashboard (admin only).

    This endpoint provides a unified view of syncs across organizations,
    useful for planning and executing vector DB migrations.

    Args:
        db: Database session
        ctx: API context
        organization_id: Optional organization filter
        search: Optional search by collection name
        limit: Maximum results

    Returns:
        List of sync info with destinations
    """
    _require_admin(ctx)

    # Build query: Sync <- SourceConnection -> Collection -> Organization
    # SourceConnection has: sync_id (FK to Sync), readable_collection_id (FK to Collection)
    query = (
        select(Sync, SourceConnection, Collection, Organization)
        .join(SourceConnection, SourceConnection.sync_id == Sync.id)
        .join(Collection, SourceConnection.readable_collection_id == Collection.readable_id)
        .join(Organization, Collection.organization_id == Organization.id)
    )

    if organization_id:
        query = query.where(Organization.id == organization_id)

    if search:
        query = query.where(Collection.name.ilike(f"%{search}%"))

    query = query.order_by(Sync.created_at.desc()).limit(limit)

    result = await db.execute(query)
    rows = result.all()

    syncs_data = []
    for sync, source_conn, collection, org in rows:
        # Get destination slots for this sync (ONLY destinations, not sources)
        from airweave.core.shared_models import IntegrationType

        slots_result = await db.execute(
            select(SyncConnection, Connection)
            .join(Connection, SyncConnection.connection_id == Connection.id)
            .where(
                and_(
                    SyncConnection.sync_id == sync.id,
                    Connection.integration_type == IntegrationType.DESTINATION,
                )
            )
        )
        slots = []
        for slot, conn in slots_result.all():
            slots.append(
                {
                    "slot_id": str(slot.id),
                    "connection_id": str(conn.id),
                    "connection_name": conn.name,
                    "role": slot.role,
                }
            )

        # Sort: active first, then shadow, then deprecated
        role_order = {"active": 0, "shadow": 1, "deprecated": 2}
        slots.sort(key=lambda x: role_order.get(x["role"], 99))

        syncs_data.append(
            {
                "sync_id": str(sync.id),
                "sync_name": sync.name,
                "collection_id": str(collection.id),
                "collection_readable_id": str(collection.readable_id),
                "collection_name": collection.name,
                "organization_id": str(org.id),
                "organization_name": org.name,
                "source_connection_id": str(source_conn.id) if source_conn else None,
                "source_short_name": source_conn.short_name if source_conn else None,
                "destination_slots": slots,
                "created_at": sync.created_at.isoformat() if sync.created_at else None,
            }
        )

    return syncs_data


@router.post("/syncs/{sync_id}/force-resync")
async def force_resync(
    sync_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> dict:
    """Force a full resync on a sync (admin only).

    This triggers a sync with force_full_sync=True, which clears cursors
    and resyncs all data from scratch.
    """
    _require_admin(ctx)

    from airweave.core.temporal_service import temporal_service

    # Direct query for admin - bypasses organization access validation
    result = await db.execute(select(Sync).where(Sync.id == sync_id))
    sync_model = result.scalar_one_or_none()
    if not sync_model:
        raise HTTPException(status_code=404, detail="Sync not found")

    # Get source connection (direct query)
    result = await db.execute(select(SourceConnection).where(SourceConnection.sync_id == sync_id))
    source_conn = result.scalar_one_or_none()
    if not source_conn:
        raise HTTPException(status_code=404, detail="Source connection not found")

    # Get collection (direct query)
    result = await db.execute(
        select(Collection).where(Collection.readable_id == source_conn.readable_collection_id)
    )
    collection_model = result.scalar_one_or_none()
    if not collection_model:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Get source's underlying connection (direct query)
    result = await db.execute(select(Connection).where(Connection.id == source_conn.connection_id))
    connection_model = result.scalar_one_or_none()
    if not connection_model:
        raise HTTPException(status_code=404, detail="Connection not found")

    # Create sync job (direct insert for admin)
    from airweave.core.shared_models import SyncJobStatus
    from airweave.models.sync_job import SyncJob as SyncJobModel

    sync_job_model = SyncJobModel(
        sync_id=sync_id,
        status=SyncJobStatus.PENDING,
        scheduled=False,
        organization_id=sync_model.organization_id,
    )
    db.add(sync_job_model)
    await db.commit()
    await db.refresh(sync_job_model)

    # Enrich sync with connection IDs for schema validation
    sync_dict = {**sync_model.__dict__}
    sync_dict.pop("_sa_instance_state", None)
    sync_dict["source_connection_id"] = source_conn.connection_id
    # Get destination connection IDs from sync_connection table
    dest_result = await db.execute(
        select(SyncConnection.connection_id).where(SyncConnection.sync_id == sync_id)
    )
    sync_dict["destination_connection_ids"] = [row[0] for row in dest_result.all()]

    sync_schema = schemas.Sync.model_validate(sync_dict)
    sync_job_schema = schemas.SyncJob.model_validate(sync_job_model, from_attributes=True)
    collection_schema = schemas.Collection.model_validate(collection_model, from_attributes=True)
    connection_schema = schemas.Connection.model_validate(connection_model, from_attributes=True)

    # Trigger Temporal workflow with force_full_sync=True
    await temporal_service.run_source_connection_workflow(
        sync=sync_schema,
        sync_job=sync_job_schema,
        collection=collection_schema,
        connection=connection_schema,
        ctx=ctx,
        force_full_sync=True,
    )

    ctx.logger.info(f"Admin triggered force resync for sync {sync_id}, job {sync_job_model.id}")
    return {"status": "started", "sync_id": str(sync_id), "sync_job_id": str(sync_job_model.id)}


# ============ COLLECTION-LEVEL DESTINATION MANAGEMENT ============


@router.get("/collections/{collection_id}/destinations")
async def list_collection_destinations(
    collection_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> dict:
    """List destination slots for a collection with consistency status (admin only).

    Returns destinations across all syncs in the collection and whether they're consistent.
    """
    _require_admin(ctx)

    from airweave.core.shared_models import IntegrationType
    from airweave.models.sync_connection import DestinationRole

    # Get collection
    result = await db.execute(select(Collection).where(Collection.id == collection_id))
    collection = result.scalar_one_or_none()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Get all syncs for this collection via SourceConnection
    syncs_result = await db.execute(
        select(Sync, SourceConnection)
        .join(SourceConnection, SourceConnection.sync_id == Sync.id)
        .where(SourceConnection.readable_collection_id == collection.readable_id)
    )
    sync_rows = syncs_result.all()

    if not sync_rows:
        return {
            "collection_id": str(collection_id),
            "collection_name": collection.name,
            "syncs_count": 0,
            "destinations": [],
            "is_consistent": True,
            "active_connection_id": None,
        }

    # Get all destination connections for these syncs
    sync_ids = [sync.id for sync, _ in sync_rows]
    dest_result = await db.execute(
        select(SyncConnection, Connection, Sync.id.label("sync_id"))
        .join(Connection, SyncConnection.connection_id == Connection.id)
        .join(Sync, SyncConnection.sync_id == Sync.id)
        .where(
            and_(
                SyncConnection.sync_id.in_(sync_ids),
                Connection.integration_type == IntegrationType.DESTINATION,
            )
        )
    )
    dest_rows = dest_result.all()

    # Group by connection_id and analyze consistency
    destinations_by_connection: dict = {}
    active_per_sync: dict = {}

    for sync_conn, conn, sync_id in dest_rows:
        conn_id = str(conn.id)
        if conn_id not in destinations_by_connection:
            destinations_by_connection[conn_id] = {
                "connection_id": conn_id,
                "connection_name": conn.name,
                "roles_by_sync": {},
            }
        destinations_by_connection[conn_id]["roles_by_sync"][str(sync_id)] = sync_conn.role

        if sync_conn.role == DestinationRole.ACTIVE.value:
            active_per_sync[str(sync_id)] = conn_id

    # Check consistency: all syncs should have the same active destination
    active_values = list(active_per_sync.values())
    is_consistent = len(set(active_values)) <= 1 and len(active_values) == len(sync_ids)
    active_connection_id = active_values[0] if is_consistent and active_values else None

    # Build response with aggregated role info
    destinations = []
    for conn_id, data in destinations_by_connection.items():
        roles = list(data["roles_by_sync"].values())
        # Determine "effective" role (most common, or mixed)
        if len(set(roles)) == 1:
            effective_role = roles[0]
        else:
            effective_role = "mixed"

        destinations.append(
            {
                "connection_id": data["connection_id"],
                "connection_name": data["connection_name"],
                "role": effective_role,
                "syncs_with_role": data["roles_by_sync"],
            }
        )

    # Sort: active first, then shadow, then deprecated, then mixed
    role_order = {"active": 0, "shadow": 1, "deprecated": 2, "mixed": 3}
    destinations.sort(key=lambda x: role_order.get(x["role"], 99))

    return {
        "collection_id": str(collection_id),
        "collection_name": collection.name,
        "syncs_count": len(sync_ids),
        "destinations": destinations,
        "is_consistent": is_consistent,
        "active_connection_id": active_connection_id,
    }


@router.post("/collections/{collection_id}/destinations/fork")
async def fork_collection_destination(
    collection_id: UUID,
    destination_connection_id: UUID,
    replay_from_arf: bool = Query(
        False, description="Replay existing data from ARF storage to the new destination"
    ),
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> dict:
    """Fork: add a shadow destination to ALL syncs in a collection (admin only).

    This ensures all syncs in the collection have the same shadow destination.
    If replay_from_arf is True, also triggers replay jobs to populate the new destination.
    """
    _require_admin(ctx)

    from airweave.core.shared_models import SyncJobStatus
    from airweave.core.temporal_service import temporal_service
    from airweave.db.unit_of_work import UnitOfWork
    from airweave.models.sync_connection import DestinationRole
    from airweave.models.sync_job import SyncJob as SyncJobModel

    # Get collection
    result = await db.execute(select(Collection).where(Collection.id == collection_id))
    collection_model = result.scalar_one_or_none()
    if not collection_model:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Validate destination connection exists
    dest_result = await db.execute(
        select(Connection).where(Connection.id == destination_connection_id)
    )
    dest_conn = dest_result.scalar_one_or_none()
    if not dest_conn:
        raise HTTPException(status_code=404, detail="Destination connection not found")

    # Get all syncs with their source connections for this collection
    syncs_result = await db.execute(
        select(Sync, SourceConnection)
        .join(SourceConnection, SourceConnection.sync_id == Sync.id)
        .where(SourceConnection.readable_collection_id == collection_model.readable_id)
    )
    sync_rows = syncs_result.all()

    if not sync_rows:
        raise HTTPException(status_code=400, detail="No syncs found for this collection")

    # Add shadow destination to each sync
    added_count = 0
    replay_jobs = []

    async with UnitOfWork(db) as uow:
        for sync_model, source_conn in sync_rows:
            # Check if this destination already exists for this sync
            existing = await db.execute(
                select(SyncConnection).where(
                    and_(
                        SyncConnection.sync_id == sync_model.id,
                        SyncConnection.connection_id == destination_connection_id,
                    )
                )
            )
            if existing.scalar_one_or_none():
                continue  # Already exists, skip

            # Create shadow slot
            slot = SyncConnection(
                sync_id=sync_model.id,
                connection_id=destination_connection_id,
                role=DestinationRole.SHADOW.value,
            )
            db.add(slot)
            added_count += 1

        await uow.commit()

    # If replay requested, trigger replay jobs for each sync
    if replay_from_arf and added_count > 0:
        for sync_model, source_conn in sync_rows:
            try:
                # Get underlying source connection
                conn_result = await db.execute(
                    select(Connection).where(Connection.id == source_conn.connection_id)
                )
                connection_model = conn_result.scalar_one_or_none()
                if not connection_model:
                    continue

                # Create replay sync job
                sync_job_model = SyncJobModel(
                    sync_id=sync_model.id,
                    status=SyncJobStatus.PENDING,
                    scheduled=False,
                    organization_id=sync_model.organization_id,
                )
                db.add(sync_job_model)
                await db.flush()

                # Enrich sync with connection IDs
                sync_dict = {**sync_model.__dict__}
                sync_dict.pop("_sa_instance_state", None)
                sync_dict["source_connection_id"] = source_conn.connection_id
                dest_ids_result = await db.execute(
                    select(SyncConnection.connection_id).where(
                        SyncConnection.sync_id == sync_model.id
                    )
                )
                sync_dict["destination_connection_ids"] = [row[0] for row in dest_ids_result.all()]

                sync_schema = schemas.Sync.model_validate(sync_dict)
                sync_job_schema = schemas.SyncJob.model_validate(
                    sync_job_model, from_attributes=True
                )
                collection_schema = schemas.Collection.model_validate(
                    collection_model, from_attributes=True
                )
                connection_schema = schemas.Connection.model_validate(
                    connection_model, from_attributes=True
                )

                # Trigger replay workflow
                await temporal_service.run_source_connection_workflow(
                    sync=sync_schema,
                    sync_job=sync_job_schema,
                    collection=collection_schema,
                    connection=connection_schema,
                    ctx=ctx,
                    replay_target_destination_id=destination_connection_id,
                )

                replay_jobs.append(
                    {
                        "sync_id": str(sync_model.id),
                        "sync_job_id": str(sync_job_model.id),
                    }
                )
            except Exception as e:
                ctx.logger.warning(f"Failed to start replay for sync {sync_model.id}: {e}")

        await db.commit()

    ctx.logger.info(
        f"Admin forked destination {destination_connection_id} to {added_count} syncs in collection {collection_id}, replay_jobs={len(replay_jobs)}"
    )
    return {
        "status": "forked",
        "collection_id": str(collection_id),
        "destination_connection_id": str(destination_connection_id),
        "syncs_updated": added_count,
        "replay_jobs": replay_jobs if replay_from_arf else None,
    }


@router.post("/collections/{collection_id}/destinations/{connection_id}/set-role")
async def set_collection_destination_role(
    collection_id: UUID,
    connection_id: UUID,
    role: str,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> dict:
    """Set the role of a destination for ALL syncs in a collection (admin only).

    When promoting to active, demotes current active to shadow across all syncs.
    Cannot demote the last active destination - there must always be at least one.
    """
    _require_admin(ctx)

    from airweave.core.shared_models import IntegrationType
    from airweave.db.unit_of_work import UnitOfWork
    from airweave.models.sync_connection import DestinationRole

    # Validate role
    try:
        new_role = DestinationRole(role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {role}")

    # Get collection
    result = await db.execute(select(Collection).where(Collection.id == collection_id))
    collection = result.scalar_one_or_none()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Get all syncs for this collection
    syncs_result = await db.execute(
        select(Sync)
        .join(SourceConnection, SourceConnection.sync_id == Sync.id)
        .where(SourceConnection.readable_collection_id == collection.readable_id)
    )
    syncs = syncs_result.scalars().all()
    sync_ids = [s.id for s in syncs]

    if not sync_ids:
        raise HTTPException(status_code=400, detail="No syncs found for this collection")

    # GUARDRAIL: If demoting from active, check if this is the only active destination
    if new_role != DestinationRole.ACTIVE:
        # Check if target is currently active
        target_check = await db.execute(
            select(SyncConnection)
            .join(Connection, SyncConnection.connection_id == Connection.id)
            .where(
                and_(
                    SyncConnection.sync_id.in_(sync_ids),
                    SyncConnection.connection_id == connection_id,
                    SyncConnection.role == DestinationRole.ACTIVE.value,
                )
            )
        )
        is_target_active = target_check.scalar_one_or_none() is not None

        if is_target_active:
            # Count other active destinations (excluding the one we're demoting)
            other_active = await db.execute(
                select(SyncConnection)
                .join(Connection, SyncConnection.connection_id == Connection.id)
                .where(
                    and_(
                        SyncConnection.sync_id.in_(sync_ids),
                        SyncConnection.role == DestinationRole.ACTIVE.value,
                        SyncConnection.connection_id != connection_id,
                        Connection.integration_type == IntegrationType.DESTINATION,
                    )
                )
            )
            if not other_active.scalar_one_or_none():
                raise HTTPException(
                    status_code=400,
                    detail="Cannot demote the last active destination. Promote another destination first.",
                )

    async with UnitOfWork(db) as uow:
        if new_role == DestinationRole.ACTIVE:
            # Demote current active destinations to shadow (across all syncs)
            await db.execute(
                SyncConnection.__table__.update()
                .where(
                    and_(
                        SyncConnection.sync_id.in_(sync_ids),
                        SyncConnection.role == DestinationRole.ACTIVE.value,
                    )
                )
                .values(role=DestinationRole.SHADOW.value)
            )

        # Set the new role for target destination across all syncs
        result = await db.execute(
            SyncConnection.__table__.update()
            .where(
                and_(
                    SyncConnection.sync_id.in_(sync_ids),
                    SyncConnection.connection_id == connection_id,
                )
            )
            .values(role=new_role.value)
        )

        await uow.commit()

    ctx.logger.info(
        f"Admin set role={role} for destination {connection_id} across {len(sync_ids)} syncs in collection {collection_id}"
    )
    return {
        "status": "updated",
        "collection_id": str(collection_id),
        "connection_id": str(connection_id),
        "role": role,
        "syncs_updated": len(sync_ids),
    }


@router.delete("/collections/{collection_id}/destinations/{connection_id}")
async def remove_collection_destination(
    collection_id: UUID,
    connection_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> dict:
    """Remove a destination from ALL syncs in a collection (admin only).

    Cannot remove the active destination.
    """
    _require_admin(ctx)

    from airweave.models.sync_connection import DestinationRole

    # Get collection
    result = await db.execute(select(Collection).where(Collection.id == collection_id))
    collection = result.scalar_one_or_none()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Get all syncs for this collection
    syncs_result = await db.execute(
        select(Sync)
        .join(SourceConnection, SourceConnection.sync_id == Sync.id)
        .where(SourceConnection.readable_collection_id == collection.readable_id)
    )
    syncs = syncs_result.scalars().all()
    sync_ids = [s.id for s in syncs]

    if not sync_ids:
        raise HTTPException(status_code=400, detail="No syncs found for this collection")

    # Check if any sync has this as active
    active_check = await db.execute(
        select(SyncConnection).where(
            and_(
                SyncConnection.sync_id.in_(sync_ids),
                SyncConnection.connection_id == connection_id,
                SyncConnection.role == DestinationRole.ACTIVE.value,
            )
        )
    )
    if active_check.scalar_one_or_none():
        raise HTTPException(
            status_code=400, detail="Cannot remove active destination - change role first"
        )

    # Delete the destination from all syncs
    result = await db.execute(
        SyncConnection.__table__.delete().where(
            and_(
                SyncConnection.sync_id.in_(sync_ids),
                SyncConnection.connection_id == connection_id,
            )
        )
    )
    await db.commit()

    ctx.logger.info(f"Admin removed destination {connection_id} from collection {collection_id}")
    return {
        "status": "removed",
        "collection_id": str(collection_id),
        "connection_id": str(connection_id),
    }


@router.get("/organizations/{organization_id}/destination-connections")
async def list_destination_connections(
    organization_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> List[dict]:
    """List available destination connections for an organization (admin only)."""
    _require_admin(ctx)

    from airweave.core.shared_models import IntegrationType

    result = await db.execute(
        select(Connection).where(
            and_(
                Connection.organization_id == organization_id,
                Connection.integration_type == IntegrationType.DESTINATION,
            )
        )
    )
    connections = result.scalars().all()

    return [
        {
            "id": str(conn.id),
            "name": conn.name,
            "short_name": conn.short_name,
        }
        for conn in connections
    ]


@router.post("/collections/{collection_id}/force-resync")
async def force_resync_collection(
    collection_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> dict:
    """Force full resync on ALL syncs in a collection (admin only).

    This triggers force_full_sync=True for each sync in the collection.
    """
    _require_admin(ctx)

    from airweave.core.shared_models import SyncJobStatus
    from airweave.core.temporal_service import temporal_service
    from airweave.models.sync_job import SyncJob as SyncJobModel

    # Get collection
    result = await db.execute(select(Collection).where(Collection.id == collection_id))
    collection_model = result.scalar_one_or_none()
    if not collection_model:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Get all syncs for this collection
    syncs_result = await db.execute(
        select(Sync, SourceConnection)
        .join(SourceConnection, SourceConnection.sync_id == Sync.id)
        .where(SourceConnection.readable_collection_id == collection_model.readable_id)
    )
    sync_rows = syncs_result.all()

    if not sync_rows:
        raise HTTPException(status_code=400, detail="No syncs found for this collection")

    jobs_started = []
    for sync_model, source_conn in sync_rows:
        # Get underlying connection
        conn_result = await db.execute(
            select(Connection).where(Connection.id == source_conn.connection_id)
        )
        connection_model = conn_result.scalar_one_or_none()
        if not connection_model:
            continue

        # Create sync job
        sync_job_model = SyncJobModel(
            sync_id=sync_model.id,
            status=SyncJobStatus.PENDING,
            scheduled=False,
            organization_id=sync_model.organization_id,
        )
        db.add(sync_job_model)
        await db.flush()

        # Enrich sync with connection IDs
        sync_dict = {**sync_model.__dict__}
        sync_dict.pop("_sa_instance_state", None)
        sync_dict["source_connection_id"] = source_conn.connection_id
        dest_result = await db.execute(
            select(SyncConnection.connection_id).where(SyncConnection.sync_id == sync_model.id)
        )
        sync_dict["destination_connection_ids"] = [row[0] for row in dest_result.all()]

        sync_schema = schemas.Sync.model_validate(sync_dict)
        sync_job_schema = schemas.SyncJob.model_validate(sync_job_model, from_attributes=True)
        collection_schema = schemas.Collection.model_validate(
            collection_model, from_attributes=True
        )
        connection_schema = schemas.Connection.model_validate(
            connection_model, from_attributes=True
        )

        # Trigger Temporal workflow
        await temporal_service.run_source_connection_workflow(
            sync=sync_schema,
            sync_job=sync_job_schema,
            collection=collection_schema,
            connection=connection_schema,
            ctx=ctx,
            force_full_sync=True,
        )

        jobs_started.append(
            {
                "sync_id": str(sync_model.id),
                "sync_job_id": str(sync_job_model.id),
            }
        )

    await db.commit()

    ctx.logger.info(
        f"Admin triggered force resync for collection {collection_id}, {len(jobs_started)} jobs started"
    )
    return {
        "status": "started",
        "collection_id": str(collection_id),
        "jobs_started": jobs_started,
    }
