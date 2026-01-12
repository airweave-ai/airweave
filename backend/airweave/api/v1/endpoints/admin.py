"""Admin-only API endpoints for organization management.

TODO: Enhance CRUD layer to support bypassing organization filtering cleanly.
Currently admin endpoints manually construct SQLAlchemy queries to bypass ctx-based
org filtering. Consider adding a `skip_org_filter=True` parameter to CRUD methods
or a dedicated `crud_admin` module for cross-org operations.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from fastapi import Body, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
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
from airweave.core.temporal_service import temporal_service
from airweave.crud.crud_organization_billing import organization_billing
from airweave.db.unit_of_work import UnitOfWork
from airweave.integrations.auth0_management import auth0_management_client
from airweave.integrations.stripe_client import stripe_client
from airweave.models.organization import Organization
from airweave.models.organization_billing import OrganizationBilling
from airweave.models.user_organization import UserOrganization
from airweave.platform.sync.config import SyncConfig
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
    # Allow both explicit admins AND superusers (for system operations and tests)
    if not ctx.has_user_context or not (ctx.user.is_admin or ctx.user.is_superuser):
        raise HTTPException(status_code=403, detail="Admin access required")


def _require_admin_permission(ctx: ApiContext, permission: FeatureFlagEnum) -> None:
    """Validate admin access with scoped API key permission support.

    This function enables CASA-compliant admin access by checking:
    1. User-based admin (traditional): User must be admin or superuser
    2. API key-based (scoped): Organization must have specific permission feature flag

    This approach provides granular, auditable admin access for programmatic operations
    while maintaining security best practices.

    Args:
        ctx: The API context
        permission: The specific permission feature flag required for API key access

    Raises:
        HTTPException: If neither user admin nor API key permission is satisfied

    Example:
        # Require API_KEY_ADMIN_SYNC for resync operations
        _require_admin_permission(ctx, FeatureFlagEnum.API_KEY_ADMIN_SYNC)
    """
    # Check 1: User-based admin (traditional path)
    if ctx.has_user_context and (ctx.user.is_admin or ctx.user.is_superuser):
        ctx.logger.debug(f"Admin access granted via user: {ctx.user.email}")
        return

    # Check 2: API key with scoped permission (CASA-compliant path)
    if ctx.is_api_key_auth and ctx.has_feature(permission):
        ctx.logger.info(
            f"Admin access granted via API key with permission: {permission.value}",
            extra={
                "permission": permission.value,
                "organization_id": str(ctx.organization.id),
                "auth_method": ctx.auth_method.value,
            },
        )
        return

    # Neither condition met - deny access
    if ctx.is_api_key_auth:
        raise HTTPException(
            status_code=403,
            detail=f"API key requires '{permission.value}' feature flag for admin access",
        )
    raise HTTPException(status_code=403, detail="Admin access required")


async def _build_org_context(
    db: AsyncSession,
    target_org_id: UUID,
    admin_ctx: ApiContext,
) -> ApiContext:
    """Build a context for a target organization (for cross-org admin operations).

    This allows admin endpoints to execute operations (CRUD, Temporal workflows) in the
    context of a different organization than the admin's API key belongs to.

    The resulting context:
    - Uses the target organization's data (id, name, feature flags)
    - Preserves admin's request_id and logger for tracing
    - Preserves auth_method and auth_metadata for audit

    Args:
        db: Database session
        target_org_id: The organization ID to build context for
        admin_ctx: The admin's original context (for logging/tracing)

    Returns:
        ApiContext configured for the target organization
    """
    from sqlalchemy import select as sa_select

    from airweave.core.logging import LoggerConfigurator

    # Fetch target organization
    org_result = await db.execute(sa_select(Organization).where(Organization.id == target_org_id))
    org_obj = org_result.scalar_one_or_none()
    if not org_obj:
        raise NotFoundException(f"Organization {target_org_id} not found")

    target_org = schemas.Organization.model_validate(org_obj, from_attributes=True)

    # Build new context with target org but preserve admin's request tracing
    return ApiContext(
        request_id=admin_ctx.request_id,
        organization=target_org,
        user=admin_ctx.user,  # Preserve user if any (for audit trail)
        auth_method=admin_ctx.auth_method,
        auth_metadata=admin_ctx.auth_metadata,
        logger=LoggerConfigurator.configure_logger(
            "airweave.admin.cross_org",
            dimensions={
                "request_id": admin_ctx.request_id,
                "organization_id": str(target_org.id),
                "organization_name": target_org.name,
                "admin_org_id": str(admin_ctx.organization.id),
                "auth_method": admin_ctx.auth_method.value,
            },
        ),
    )


def _build_sort_subqueries(query, sort_by: str):
    """Build sort subqueries based on sort_by field.

    Args:
        query: The base SQLAlchemy query to extend
        sort_by: Field to sort by

    Returns:
        Tuple of (query, subqueries_dict) where subqueries_dict contains named subqueries.
    """
    from datetime import datetime

    from sqlalchemy import select as sa_select

    from airweave.models.billing_period import BillingPeriod
    from airweave.models.source_connection import SourceConnection
    from airweave.models.usage import Usage
    from airweave.models.user import User
    from airweave.schemas.billing_period import BillingPeriodStatus

    subqueries = {}

    # For usage-based sorting, join Usage and BillingPeriod
    if sort_by in ["entity_count", "query_count"]:
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
        subqueries["Usage"] = Usage

    # For user_count sorting
    if sort_by == "user_count":
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
        subqueries["user_count_subq"] = user_count_subq

    # For source_connection_count sorting
    if sort_by == "source_connection_count":
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
        subqueries["source_connection_count_subq"] = source_connection_count_subq

    # For last_active_at sorting
    if sort_by == "last_active_at":
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
        subqueries["max_active_subq"] = max_active_subq

    return query, subqueries


def _get_sort_column(sort_by: str, subqueries: dict):
    """Get the SQLAlchemy column to sort by."""
    from airweave.models.usage import Usage

    # Map sort_by to column
    column_map = {
        "billing_plan": OrganizationBilling.billing_plan,
        "billing_status": OrganizationBilling.billing_status,
        "entity_count": Usage.entities,
        "query_count": Usage.queries,
        "is_member": Organization.created_at,  # Handled client-side
    }

    if sort_by in column_map:
        return column_map[sort_by]
    if sort_by == "user_count" and "user_count_subq" in subqueries:
        return subqueries["user_count_subq"].c.user_count
    if sort_by == "source_connection_count" and "source_connection_count_subq" in subqueries:
        return subqueries["source_connection_count_subq"].c.source_connection_count
    if sort_by == "last_active_at" and "max_active_subq" in subqueries:
        return subqueries["max_active_subq"].c.max_last_active
    if hasattr(Organization, sort_by):
        return getattr(Organization, sort_by)
    return Organization.created_at  # Default


async def _update_or_create_membership(
    db: AsyncSession, ctx: ApiContext, organization_id: UUID, role: str
) -> bool:
    """Update existing membership or create new one. Returns True if membership changed."""
    # Check if user is already a member
    existing_user_org = None
    for user_org in ctx.user.user_organizations:
        if user_org.organization.id == organization_id:
            existing_user_org = user_org
            break

    if existing_user_org:
        return await _update_membership_role(db, ctx, organization_id, role, existing_user_org)

    return await _create_new_membership(db, ctx, organization_id, role)


async def _update_membership_role(
    db: AsyncSession, ctx: ApiContext, organization_id: UUID, role: str, existing_user_org
) -> bool:
    """Update role if different, return True if changed."""
    if existing_user_org.role == role:
        ctx.logger.info(
            f"Admin {ctx.user.email} already member of org {organization_id} with role {role}"
        )
        return False

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
    ctx.logger.info(f"Admin {ctx.user.email} updated role in org {organization_id} to {role}")
    return True


async def _create_new_membership(
    db: AsyncSession, ctx: ApiContext, organization_id: UUID, role: str
) -> bool:
    """Create new membership, return True if successful."""
    try:
        user_org = UserOrganization(
            user_id=ctx.user.id,
            organization_id=organization_id,
            role=role,
            is_primary=False,
        )
        db.add(user_org)
        await db.commit()
        ctx.logger.info(
            f"Admin {ctx.user.email} added self to org {organization_id} with role {role}"
        )
        return True
    except Exception as e:
        ctx.logger.error(f"Failed to add admin to organization: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to add user to organization: {str(e)}")


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

    # Build the base query with billing join
    query = select(Organization).outerjoin(
        OrganizationBilling, Organization.id == OrganizationBilling.organization_id
    )

    # Build sort subqueries based on sort_by field
    query, subqueries = _build_sort_subqueries(query, sort_by)

    # Apply search filter
    if search:
        query = query.where(Organization.name.ilike(f"%{search}%"))

    # Apply sorting (is_member sorting handled client-side)
    sort_column = _get_sort_column(sort_by, subqueries)

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

    membership_changed = await _update_or_create_membership(db, ctx, organization_id, role)

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


@router.post("/resync/{sync_id}", response_model=schemas.SyncJob)
async def resync_with_execution_config(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    ctx: ApiContext = Depends(deps.get_context),
    execution_config: Optional[SyncConfig] = Body(
        None,
        description="Optional nested SyncConfig for sync behavior (destinations, handlers, cursor, behavior)",
        examples=[
            {
                "summary": "ARF Capture Only",
                "value": {
                    "handlers": {
                        "enable_vector_handlers": False,
                        "enable_postgres_handler": False,
                        "enable_raw_data_handler": True,
                    },
                    "cursor": {"skip_load": True, "skip_updates": True},
                    "behavior": {"skip_hash_comparison": True},
                },
            },
            {
                "summary": "ARF Replay to Vector DBs",
                "value": {
                    "handlers": {
                        "enable_vector_handlers": True,
                        "enable_postgres_handler": False,
                        "enable_raw_data_handler": False,
                    },
                    "cursor": {"skip_load": True, "skip_updates": True},
                    "behavior": {"skip_hash_comparison": True, "replay_from_arf": True},
                },
            },
            {
                "summary": "Skip Vespa",
                "value": {"destinations": {"skip_vespa": True}},
            },
        ],
    ),
) -> schemas.SyncJob:
    """Admin-only: Trigger a sync with custom execution config via Temporal.

    This endpoint allows admins to trigger syncs with custom execution configurations
    for advanced use cases like ARF-only capture, destination-specific replays, or dry runs.

    The sync is dispatched to Temporal and runs asynchronously in workers, not in the backend pod.

    **API Key Access**: Organizations with the `api_key_admin_sync` feature flag enabled
    can use API keys to access this endpoint programmatically.

    **Config Structure**: Nested config with 4 sub-objects:
        - destinations: skip_qdrant, skip_vespa, target_destinations, exclude_destinations
        - handlers: enable_vector_handlers, enable_raw_data_handler, enable_postgres_handler
        - cursor: skip_load, skip_updates
        - behavior: skip_hash_comparison, replay_from_arf

    Args:
        db: Database session
        sync_id: ID of the sync to trigger
        ctx: API context
        execution_config: Optional nested SyncConfig

    Returns:
        The created sync job

    Raises:
        HTTPException: If user is not admin or sync not found

    **Preset Examples** (use SyncConfig factory methods):
        - Normal sync: SyncConfig.default()
        - ARF capture only: SyncConfig.arf_capture_only()
        - ARF replay to vector DBs: SyncConfig.replay_from_arf_to_vector_dbs()
        - Qdrant only: SyncConfig.qdrant_only()
        - Vespa only: SyncConfig.vespa_only()
    """
    _require_admin_permission(ctx, FeatureFlagEnum.API_KEY_ADMIN_SYNC)

    ctx.logger.info(
        f"Admin triggering resync for sync {sync_id} with execution config: {execution_config}"
    )

    # Bypass organization filtering for all queries (admin access)
    from sqlalchemy import select as sa_select

    from airweave.core.shared_models import IntegrationType, SyncJobStatus
    from airweave.db.unit_of_work import UnitOfWork
    from airweave.models.collection import Collection
    from airweave.models.connection import Connection
    from airweave.models.source_connection import SourceConnection
    from airweave.models.sync import Sync
    from airweave.models.sync_connection import SyncConnection
    from airweave.models.sync_job import SyncJob

    # Get the sync without organization filtering
    result = await db.execute(sa_select(Sync).where(Sync.id == sync_id))
    sync_obj = result.scalar_one_or_none()
    if not sync_obj:
        raise NotFoundException(f"Sync {sync_id} not found")

    # Capture organization_id immediately before other async operations expire the model
    sync_organization_id = sync_obj.organization_id

    # Get connection IDs from SyncConnection table (bypass org filtering)
    sync_connections_result = await db.execute(
        sa_select(SyncConnection, Connection)
        .join(Connection, SyncConnection.connection_id == Connection.id)
        .where(SyncConnection.sync_id == sync_id)
    )
    sync_connections = sync_connections_result.all()

    source_connection_id = None
    destination_connection_ids = []
    for _sync_conn, conn in sync_connections:
        if conn.integration_type == IntegrationType.SOURCE:
            source_connection_id = conn.id
        else:
            destination_connection_ids.append(conn.id)

    if not source_connection_id:
        raise NotFoundException(f"Source connection not found for sync {sync_id}")

    # Check for existing active jobs (bypass org filtering)
    active_jobs_result = await db.execute(
        sa_select(SyncJob).where(
            SyncJob.sync_id == sync_id,
            SyncJob.status.in_(
                [
                    SyncJobStatus.PENDING,
                    SyncJobStatus.RUNNING,
                    SyncJobStatus.CANCELLING,
                ]
            ),
        )
    )
    active_jobs = list(active_jobs_result.scalars().all())
    if active_jobs:
        status = active_jobs[0].status
        job_status = (status.value if hasattr(status, "value") else status).lower()
        raise HTTPException(
            status_code=400, detail=f"Cannot start new sync: a sync job is already {job_status}"
        )

    # Enrich sync dict with connection IDs for schema validation
    sync_dict = {
        "id": sync_obj.id,
        "organization_id": sync_obj.organization_id,
        "name": sync_obj.name,
        "description": sync_obj.description,
        "status": sync_obj.status,
        "cron_schedule": sync_obj.cron_schedule,
        "next_scheduled_run": sync_obj.next_scheduled_run,
        "temporal_schedule_id": sync_obj.temporal_schedule_id,
        "sync_type": sync_obj.sync_type,
        "sync_metadata": sync_obj.sync_metadata,
        "created_at": sync_obj.created_at,
        "modified_at": sync_obj.modified_at,
        "created_by_email": sync_obj.created_by_email,
        "modified_by_email": sync_obj.modified_by_email,
        "source_connection_id": source_connection_id,
        "destination_connection_ids": destination_connection_ids,
    }
    sync_schema = schemas.Sync.model_validate(sync_dict)
    async with UnitOfWork(db) as uow:
        sync_job_obj = SyncJob(
            sync_id=sync_id,
            organization_id=sync_obj.organization_id,
            status=SyncJobStatus.PENDING,
            sync_config=execution_config.model_dump() if execution_config else None,
        )
        uow.session.add(sync_job_obj)
        await uow.commit()
        await uow.session.refresh(sync_job_obj)

    sync_job_schema = schemas.SyncJob.model_validate(sync_job_obj, from_attributes=True)

    # Get source connection (bypass org filtering)
    source_conn_result = await db.execute(
        sa_select(SourceConnection).where(SourceConnection.sync_id == sync_id)
    )
    source_conn = source_conn_result.scalar_one_or_none()
    if not source_conn:
        raise NotFoundException(f"Source connection not found for sync {sync_id}")

    # Get collection (bypass org filtering)
    collection_result = await db.execute(
        sa_select(Collection).where(Collection.readable_id == source_conn.readable_collection_id)
    )
    collection = collection_result.scalar_one_or_none()
    if not collection:
        raise NotFoundException(f"Collection {source_conn.readable_collection_id} not found")

    collection_schema = schemas.Collection.model_validate(collection, from_attributes=True)

    # Get the Connection object (bypass org filtering)
    connection_result = await db.execute(
        sa_select(Connection).where(Connection.id == source_conn.connection_id)
    )
    connection = connection_result.scalar_one_or_none()
    if not connection:
        raise NotFoundException("Connection not found for source connection")
    connection_schema = schemas.Connection.model_validate(connection, from_attributes=True)

    # Build context for the sync's organization (not the admin's API key org)
    # This ensures Temporal workers can access resources in the correct org context
    sync_org_ctx = await _build_org_context(db, sync_organization_id, ctx)

    # Dispatch to Temporal with the sync's organization context
    ctx.logger.info(
        f"Dispatching sync job {sync_job_schema.id} to Temporal "
        f"(sync org: {sync_organization_id}, admin org: {ctx.organization.id})"
    )
    await temporal_service.run_source_connection_workflow(
        sync=sync_schema,
        sync_job=sync_job_schema,
        collection=collection_schema,
        connection=connection_schema,
        ctx=sync_org_ctx,  # Use sync's org context, not admin's
        force_full_sync=False,
    )

    ctx.logger.info(f"✅ Admin resync job {sync_job_schema.id} dispatched to Temporal")

    return sync_job_schema


# =============================================================================
# Admin Sync Endpoints for API Key Access
# =============================================================================


class AdminSyncInfo(schemas.Sync):
    """Extended sync info for admin listing with entity counts and status."""

    total_entity_count: int = 0
    total_arf_entity_count: Optional[int] = None
    total_qdrant_entity_count: Optional[int] = None
    total_vespa_entity_count: Optional[int] = None

    last_job_status: Optional[str] = None
    last_job_at: Optional[datetime] = None
    last_job_error: Optional[str] = None
    source_short_name: Optional[str] = None
    source_is_authenticated: Optional[bool] = None
    readable_collection_id: Optional[str] = None

    # Last job that wrote to Vespa (skip_vespa != true)
    last_vespa_job_id: Optional[UUID] = None
    last_vespa_job_status: Optional[str] = None
    last_vespa_job_at: Optional[datetime] = None

    class Config:
        """Pydantic config."""

        from_attributes = True


class AdminSearchDestination(str, Enum):
    """Destination options for admin search."""

    QDRANT = "qdrant"
    VESPA = "vespa"


@router.post("/collections/{readable_id}/search", response_model=schemas.SearchResponse)
async def admin_search_collection(
    readable_id: str,
    search_request: schemas.SearchRequest,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    destination: AdminSearchDestination = Query(
        AdminSearchDestination.QDRANT,
        description="Search destination: 'qdrant' (default) or 'vespa'",
    ),
) -> schemas.SearchResponse:
    """Admin-only: Search any collection regardless of organization.

    This endpoint allows admins or API keys with `api_key_admin_sync` permission
    to search collections across organizations for migration and support purposes.

    Supports selecting the search destination (Qdrant or Vespa) for migration testing.

    Args:
        readable_id: The readable ID of the collection to search
        search_request: The search request parameters
        db: Database session
        ctx: API context
        destination: Search destination ('qdrant' or 'vespa')

    Returns:
        SearchResponse with results

    Raises:
        HTTPException: If not admin or collection not found
    """
    import time

    from sqlalchemy import select as sa_select

    from airweave.models.collection import Collection
    from airweave.search.orchestrator import orchestrator

    _require_admin_permission(ctx, FeatureFlagEnum.API_KEY_ADMIN_SYNC)

    # Get collection without organization filtering
    result = await db.execute(sa_select(Collection).where(Collection.readable_id == readable_id))
    collection = result.scalar_one_or_none()

    if not collection:
        raise NotFoundException(f"Collection '{readable_id}' not found")

    ctx.logger.info(
        f"Admin searching collection {readable_id} (org: {collection.organization_id}) "
        f"using destination: {destination.value}"
    )

    start_time = time.monotonic()

    # Create destination based on selection
    dest_instance = await _create_admin_search_destination(
        destination=destination,
        collection_id=collection.id,
        organization_id=collection.organization_id,
        vector_size=collection.vector_size,
        ctx=ctx,
    )

    # Build search context with custom destination factory
    search_context = await _build_admin_search_context(
        db=db,
        collection=collection,
        readable_id=readable_id,
        search_request=search_request,
        destination=dest_instance,
        ctx=ctx,
    )

    # Execute search
    ctx.logger.debug("Executing admin search")
    response, state = await orchestrator.run(ctx, search_context)

    duration_ms = (time.monotonic() - start_time) * 1000

    ctx.logger.info(
        f"Admin search completed for collection {readable_id} ({destination.value}): "
        f"{len(response.results)} results in {duration_ms:.2f}ms"
    )

    return response


async def _create_admin_search_destination(
    destination: AdminSearchDestination,
    collection_id: UUID,
    organization_id: UUID,
    vector_size: int,
    ctx: ApiContext,
):
    """Create destination instance for admin search.

    Args:
        destination: Which destination to use
        collection_id: Collection UUID
        organization_id: Organization UUID
        vector_size: Vector dimensions
        ctx: API context

    Returns:
        Destination instance (Qdrant or Vespa)
    """
    if destination == AdminSearchDestination.VESPA:
        from airweave.platform.destinations.vespa import VespaDestination

        ctx.logger.info("Creating Vespa destination for admin search")
        return await VespaDestination.create(
            collection_id=collection_id,
            organization_id=organization_id,
            vector_size=vector_size,
            logger=ctx.logger,
        )
    else:
        from airweave.platform.destinations.qdrant import QdrantDestination

        ctx.logger.info("Creating Qdrant destination for admin search")
        return await QdrantDestination.create(
            collection_id=collection_id,
            organization_id=organization_id,
            vector_size=vector_size,
            logger=ctx.logger,
        )


async def _build_admin_search_context(
    db: AsyncSession,
    collection,
    readable_id: str,
    search_request: schemas.SearchRequest,
    destination,
    ctx: ApiContext,
):
    """Build search context with custom destination for admin search.

    This mirrors the factory.build() but allows overriding the destination.
    """
    from airweave.search.factory import (
        SearchContext,
        factory,
    )

    # Apply defaults and validate
    params = factory._apply_defaults_and_validate(search_request)

    # Get collection sources
    federated_sources = await factory.get_federated_sources(db, collection, ctx)
    has_federated_sources = bool(federated_sources)
    has_vector_sources = await factory._has_vector_sources(db, collection, ctx)

    # Determine destination capabilities
    requires_embedding = getattr(destination, "_requires_client_embedding", True)
    supports_temporal = getattr(destination, "_supports_temporal_relevance", True)

    ctx.logger.info(
        f"[AdminSearch] Destination: {destination.__class__.__name__}, "
        f"requires_client_embedding: {requires_embedding}, "
        f"supports_temporal_relevance: {supports_temporal}"
    )

    if not has_federated_sources and not has_vector_sources:
        raise ValueError("Collection has no sources")

    vector_size = collection.vector_size
    if vector_size is None:
        raise ValueError(f"Collection {collection.readable_id} has no vector_size set.")

    # Select providers for operations
    api_keys = factory._get_available_api_keys()
    providers = factory._create_provider_for_each_operation(
        api_keys,
        params,
        has_federated_sources,
        has_vector_sources,
        ctx,
        vector_size,
        requires_client_embedding=requires_embedding,
    )

    # Create event emitter
    from airweave.search.emitter import EventEmitter

    emitter = EventEmitter(request_id=ctx.request_id, stream=False)

    # Get temporal supporting sources if needed
    temporal_supporting_sources = None
    if params["temporal_weight"] > 0 and has_vector_sources and supports_temporal:
        try:
            temporal_supporting_sources = await factory._get_temporal_supporting_sources(
                db, collection, ctx, emitter
            )
        except Exception as e:
            raise ValueError(f"Failed to check temporal relevance support: {e}") from e
    elif params["temporal_weight"] > 0 and not supports_temporal:
        ctx.logger.info(
            "[AdminSearch] Skipping temporal relevance: destination does not support it"
        )
        temporal_supporting_sources = []

    # Build operations with custom destination
    operations = factory._build_operations(
        params,
        providers,
        federated_sources,
        has_vector_sources,
        search_request,
        temporal_supporting_sources,
        vector_size,
        destination=destination,
        requires_client_embedding=requires_embedding,
        db=db,
        ctx=ctx,
    )

    return SearchContext(
        request_id=ctx.request_id,
        collection_id=collection.id,
        readable_collection_id=readable_id,
        stream=False,
        vector_size=vector_size,
        offset=params["offset"],
        limit=params["limit"],
        emitter=emitter,
        query=search_request.query,
        **operations,
    )


@router.get("/syncs", response_model=List[AdminSyncInfo])
async def admin_list_all_syncs(
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    skip: int = Query(0, description="Number of syncs to skip"),
    limit: int = Query(100, le=1000, description="Maximum number of syncs to return"),
    sync_ids: Optional[str] = Query(
        None, description="Comma-separated list of sync IDs to filter by"
    ),
    organization_id: Optional[UUID] = Query(None, description="Filter by organization ID"),
    collection_id: Optional[str] = Query(
        None, description="Filter by collection readable ID (exact match)"
    ),
    source_type: Optional[str] = Query(None, description="Filter by source short name"),
    has_source_connection: bool = Query(
        True,
        description="Include only syncs with source connections (excludes orphaned syncs by default)",
    ),
    is_authenticated: Optional[bool] = Query(
        None,
        description="Filter by source connection authentication status (true=authenticated, false=needs reauth)",
    ),
    status: Optional[str] = Query(
        None, description="Filter by sync status (active, inactive, error)"
    ),
    last_job_status: Optional[str] = Query(
        None,
        description="Filter by last job status (completed, failed, running, pending, cancelled)",
    ),
    last_vespa_job_status: Optional[str] = Query(
        None, description="Filter by last Vespa job status (completed, failed, running, pending)"
    ),
    has_vespa_job: Optional[bool] = Query(
        None,
        description="Filter by Vespa job existence (false=pending backfill, true=has job)",
    ),
    ghost_syncs_last_n: Optional[int] = Query(
        None,
        ge=1,
        le=10,
        description="Filter to 'ghost syncs' - syncs where the last N jobs all failed (e.g., 5 for last 5 failures)",
    ),
    include_destination_counts: bool = Query(
        False,
        description="Include Qdrant and Vespa document counts (slower, queries destinations)",
    ),
    include_arf_counts: bool = Query(
        False,
        description="Include ARF entity counts (slower, queries ARF storage for each sync)",
    ),
) -> List[AdminSyncInfo]:
    """Admin-only: List all syncs across organizations with entity counts.

    Supports extensive filtering for migration and monitoring purposes.

    **Note**: Orphaned syncs (deleted source connections) are excluded by default.
    Set `has_source_connection=false` to see only orphaned syncs.

    **All filters are optional** except `has_source_connection` which defaults to true.

    **Entity Counts**:
        - total_entity_count: Count from Postgres (EntityCount table) - always included
        - total_arf_entity_count: Count from ARF storage (None unless include_arf_counts=true)
        - total_qdrant_entity_count: Count from Qdrant (None unless include_destination_counts=true)
        - total_vespa_entity_count: Count from Vespa (None unless include_destination_counts=true)

    Filters:
        - sync_ids: Comma-separated list of sync UUIDs (e.g., 'uuid1,uuid2,uuid3')
        - organization_id: Filter by organization UUID
        - collection_id: Filter by collection readable ID (exact match)
        - source_type: Filter by source short name (e.g., 'linear', 'github')
        - has_source_connection: Include syncs with source connections (default: true)
        - is_authenticated: Filter by authentication status (true=active, false=needs reauth)
        - status: Filter by sync status (active, inactive, error)
        - last_job_status: Filter by last job status (any job type)
        - last_vespa_job_status: Filter by last Vespa job status for migration tracking
        - has_vespa_job: Filter by Vespa job existence (false=pending backfill)
        - exclude_failed_last_n: Exclude syncs where last N non-running jobs all failed
        - include_destination_counts: Include Qdrant/Vespa counts (slower, queries destinations)

    **Performance Note**: Setting `include_destination_counts=true` or `include_arf_counts=true`
    queries external storage for each sync, which is significantly slower. Both default to false.
    Recommended only for small result sets (<20 syncs).

    Args:
        db: Database session
        ctx: API context
        skip: Number of syncs to skip for pagination
        limit: Maximum number of syncs to return
        sync_ids: Optional comma-separated list of sync IDs
        organization_id: Optional filter by organization ID
        collection_id: Optional filter by collection readable ID
        source_type: Optional filter by source short name
        has_source_connection: Include syncs with source connections (default true)
        is_authenticated: Optional filter by authentication status
        status: Optional filter by sync status
        last_job_status: Optional filter by last job status
        last_vespa_job_status: Optional filter by Vespa job status
        has_vespa_job: Optional filter by Vespa job existence
        exclude_failed_last_n: Optional exclude syncs with N consecutive failures
        include_destination_counts: Whether to fetch Qdrant/Vespa counts (slower)
        include_arf_counts: Whether to fetch ARF entity counts (slower)

    Returns:
        List of syncs with extended information including entity counts

    Raises:
        HTTPException: If not admin
    """
    from sqlalchemy import func
    from sqlalchemy import select as sa_select

    from airweave.core.shared_models import SyncStatus
    from airweave.models.connection import Connection
    from airweave.models.entity_count import EntityCount
    from airweave.models.source_connection import SourceConnection
    from airweave.models.sync import Sync
    from airweave.models.sync_connection import SyncConnection
    from airweave.models.sync_job import SyncJob

    import time

    _require_admin_permission(ctx, FeatureFlagEnum.API_KEY_ADMIN_SYNC)

    request_start = time.monotonic()
    timings = {}

    # Parse sync_ids if provided
    parsed_sync_ids: Optional[List[UUID]] = None
    if sync_ids:
        try:
            parsed_sync_ids = [UUID(sid.strip()) for sid in sync_ids.split(",") if sid.strip()]
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid sync_ids format. Must be comma-separated UUIDs: {e}",
            )

    # Build base query for syncs
    query = sa_select(Sync)

    # Apply SQL-level filters
    if parsed_sync_ids:
        query = query.where(Sync.id.in_(parsed_sync_ids))

    if organization_id:
        query = query.where(Sync.organization_id == organization_id)

    if status is not None:
        # Validate status value
        try:
            status_enum = SyncStatus(status.lower())
            query = query.where(Sync.status == status_enum)
        except ValueError:
            # Invalid status value, return empty result
            return []

    # Source connection filters using subqueries to avoid JOIN duplication
    if has_source_connection:
        # Only syncs that have a source connection
        query = query.where(
            Sync.id.in_(
                sa_select(SourceConnection.sync_id).where(SourceConnection.sync_id.isnot(None))
            )
        )
    else:
        # Only orphaned syncs (no source connection)
        query = query.where(
            Sync.id.notin_(
                sa_select(SourceConnection.sync_id).where(SourceConnection.sync_id.isnot(None))
            )
        )

    if is_authenticated is not None:
        query = query.where(
            Sync.id.in_(
                sa_select(SourceConnection.sync_id).where(
                    SourceConnection.is_authenticated == is_authenticated
                )
            )
        )

    if collection_id is not None:
        query = query.where(
            Sync.id.in_(
                sa_select(SourceConnection.sync_id).where(
                    SourceConnection.readable_collection_id == collection_id
                )
            )
        )

    if source_type is not None:
        query = query.where(
            Sync.id.in_(
                sa_select(SourceConnection.sync_id).where(
                    SourceConnection.short_name == source_type
                )
            )
        )

    # Apply last job status filter at SQL level
    if last_job_status is not None:
        from airweave.core.shared_models import SyncJobStatus

        try:
            status_enum = SyncJobStatus(last_job_status.lower())

            # Subquery to get most recent job per sync
            latest_job_subq = sa_select(
                SyncJob.sync_id,
                SyncJob.status,
                func.row_number()
                .over(partition_by=SyncJob.sync_id, order_by=SyncJob.created_at.desc())
                .label("rn"),
            ).subquery()

            # Filter to syncs where most recent job has the requested status
            query = query.where(
                Sync.id.in_(
                    sa_select(latest_job_subq.c.sync_id).where(
                        latest_job_subq.c.rn == 1,
                        latest_job_subq.c.status == status_enum,
                    )
                )
            )
        except ValueError:
            # Invalid status value, return empty result
            return []

    # Apply ghost sync filter at SQL level if requested
    if ghost_syncs_last_n is not None and ghost_syncs_last_n > 0:
        from airweave.core.shared_models import SyncJobStatus

        # Subquery to get last N jobs per sync (excluding running/pending)
        jobs_subq = (
            sa_select(
                SyncJob.sync_id,
                SyncJob.status,
                func.row_number()
                .over(partition_by=SyncJob.sync_id, order_by=SyncJob.created_at.desc())
                .label("rn"),
            )
            .where(
                SyncJob.status.notin_([SyncJobStatus.RUNNING.value, SyncJobStatus.PENDING.value])
            )
            .subquery()
        )

        # Get syncs where all last N jobs failed
        failed_syncs_subq = (
            sa_select(jobs_subq.c.sync_id)
            .where(jobs_subq.c.rn <= ghost_syncs_last_n)
            .group_by(jobs_subq.c.sync_id)
            .having(
                func.count().filter(jobs_subq.c.status == SyncJobStatus.FAILED.value)
                == func.count()
            )
            .having(func.count() >= ghost_syncs_last_n)
            .subquery()
        )

        query = query.where(Sync.id.in_(sa_select(failed_syncs_subq.c.sync_id)))

    # Apply Vespa job filters at SQL level (must happen before limit/offset)
    if last_vespa_job_status is not None or has_vespa_job is not None:
        # Build subquery for Vespa jobs (ARF -> Vespa replays)
        vespa_jobs_subq = (
            sa_select(
                SyncJob.sync_id,
                SyncJob.status,
                func.row_number()
                .over(partition_by=SyncJob.sync_id, order_by=SyncJob.created_at.desc())
                .label("rn"),
            )
            .where(
                SyncJob.sync_config.isnot(None),
                SyncJob.sync_config["behavior"]["replay_from_arf"].astext == "true",
                or_(
                    SyncJob.sync_config["destinations"]["skip_vespa"].astext != "true",
                    SyncJob.sync_config["destinations"]["skip_vespa"].is_(None),
                ),
            )
            .subquery()
        )

        # Get most recent Vespa job per sync
        latest_vespa_jobs = (
            sa_select(vespa_jobs_subq.c.sync_id, vespa_jobs_subq.c.status)
            .where(vespa_jobs_subq.c.rn == 1)
            .subquery()
        )

        if has_vespa_job is not None:
            if has_vespa_job:
                # Only syncs with a Vespa job
                query = query.where(Sync.id.in_(sa_select(latest_vespa_jobs.c.sync_id)))
            else:
                # Only syncs without a Vespa job (pending backfill)
                query = query.where(Sync.id.notin_(sa_select(latest_vespa_jobs.c.sync_id)))

        if last_vespa_job_status is not None:
            # Filter by specific Vespa job status
            from airweave.core.shared_models import SyncJobStatus

            try:
                status_enum = SyncJobStatus(last_vespa_job_status.lower())
                query = query.where(
                    Sync.id.in_(
                        sa_select(latest_vespa_jobs.c.sync_id).where(
                            latest_vespa_jobs.c.status == status_enum
                        )
                    )
                )
            except ValueError:
                # Invalid status value, return empty result
                return []

    query = query.order_by(Sync.created_at.desc()).offset(skip).limit(limit)

    query_start = time.monotonic()
    result = await db.execute(query)
    syncs = list(result.scalars().all())
    timings["main_query"] = (time.monotonic() - query_start) * 1000

    if not syncs:
        ctx.logger.info("Admin syncs query returned 0 results")
        return []

    sync_ids = [s.id for s in syncs]

    # Fetch entity counts in bulk
    entity_start = time.monotonic()
    entity_count_query = (
        sa_select(EntityCount.sync_id, func.sum(EntityCount.count).label("total_count"))
        .where(EntityCount.sync_id.in_(sync_ids))
        .group_by(EntityCount.sync_id)
    )
    entity_count_result = await db.execute(entity_count_query)
    entity_count_map = {row.sync_id: row.total_count or 0 for row in entity_count_result}
    timings["entity_counts"] = (time.monotonic() - entity_start) * 1000

    # Fetch ARF entity counts if requested (slower, queries ARF storage)
    if include_arf_counts:
        import asyncio

        from airweave.platform.sync.arf.service import ArfService

        arf_start = time.monotonic()
        arf_service = ArfService()

        # Parallelize ARF counts for all syncs
        async def get_arf_count_safe(sync_id):
            try:
                return await arf_service.get_entity_count(str(sync_id))
            except Exception:
                return None

        arf_count_tasks = [get_arf_count_safe(sync.id) for sync in syncs]
        arf_counts = await asyncio.gather(*arf_count_tasks)
        arf_count_map = {sync.id: count for sync, count in zip(syncs, arf_counts)}
        timings["arf_counts"] = (time.monotonic() - arf_start) * 1000
    else:
        arf_count_map = {s.id: None for s in syncs}
        timings["arf_counts"] = 0

    # Fetch last job info in bulk (including error message)
    last_job_start = time.monotonic()
    last_job_subq = (
        sa_select(
            SyncJob.sync_id,
            SyncJob.status,
            SyncJob.completed_at,
            SyncJob.error,
            func.row_number()
            .over(partition_by=SyncJob.sync_id, order_by=SyncJob.created_at.desc())
            .label("rn"),
        )
        .where(SyncJob.sync_id.in_(sync_ids))
        .subquery()
    )
    last_job_query = sa_select(last_job_subq).where(last_job_subq.c.rn == 1)
    last_job_result = await db.execute(last_job_query)
    last_job_map = {
        row.sync_id: {
            "status": row.status,
            "completed_at": row.completed_at,
            "error": row.error,
        }
        for row in last_job_result
    }
    timings["last_job_info"] = (time.monotonic() - last_job_start) * 1000

    # Fetch source connections info in bulk with collection IDs
    from airweave.models.collection import Collection

    source_conn_start = time.monotonic()
    source_conn_query = (
        sa_select(
            SourceConnection.sync_id,
            SourceConnection.short_name,
            SourceConnection.readable_collection_id,
            SourceConnection.is_authenticated,
            Collection.id.label("collection_id"),
        )
        .outerjoin(Collection, SourceConnection.readable_collection_id == Collection.readable_id)
        .where(SourceConnection.sync_id.in_(sync_ids))
    )
    source_conn_result = await db.execute(source_conn_query)
    source_conn_map = {
        row.sync_id: {
            "short_name": row.short_name,
            "readable_collection_id": row.readable_collection_id,
            "is_authenticated": row.is_authenticated,
            "collection_id": row.collection_id,
        }
        for row in source_conn_result
    }
    timings["source_connections"] = (time.monotonic() - source_conn_start) * 1000

    # Fetch Qdrant and Vespa counts if requested (slower, queries destinations)
    if include_destination_counts:
        dest_start = time.monotonic()
        qdrant_count_map, vespa_count_map = await _fetch_destination_counts(
            syncs, source_conn_map, ctx
        )
        timings["destination_counts"] = (time.monotonic() - dest_start) * 1000
    else:
        qdrant_count_map = {s.id: None for s in syncs}
        vespa_count_map = {s.id: None for s in syncs}
        timings["destination_counts"] = 0

    # Fetch sync connections to enrich with connection IDs
    sync_conn_start = time.monotonic()
    sync_conn_query = (
        sa_select(SyncConnection, Connection)
        .join(Connection, SyncConnection.connection_id == Connection.id)
        .where(SyncConnection.sync_id.in_(sync_ids))
    )
    sync_conn_result = await db.execute(sync_conn_query)
    sync_connections = {}
    for sync_conn, connection in sync_conn_result:
        sync_id = sync_conn.sync_id
        if sync_id not in sync_connections:
            sync_connections[sync_id] = {"source": None, "destinations": []}
        if connection.integration_type.value == "source":
            sync_connections[sync_id]["source"] = connection.id
        elif connection.integration_type.value == "destination":
            sync_connections[sync_id]["destinations"].append(connection.id)
    timings["sync_connections"] = (time.monotonic() - sync_conn_start) * 1000

    # Fetch last ARF -> Vespa replay job info in bulk
    # An ARF -> Vespa replay job has:
    #   - replay_from_arf=true (read from ARF storage)
    #   - skip_vespa is NOT true (writes to Vespa)
    vespa_job_start = time.monotonic()
    arf_to_vespa_job_query = (
        sa_select(
            SyncJob.id,
            SyncJob.sync_id,
            SyncJob.status,
            SyncJob.created_at,
            SyncJob.completed_at,
            SyncJob.sync_config,
        )
        .where(
            SyncJob.sync_id.in_(sync_ids),
            SyncJob.sync_config.isnot(None),
            # Must be replay from ARF
            SyncJob.sync_config["behavior"]["replay_from_arf"].astext == "true",
            # Must NOT skip Vespa (skip_vespa is absent or false)
            or_(
                SyncJob.sync_config["destinations"]["skip_vespa"].astext != "true",
                SyncJob.sync_config["destinations"]["skip_vespa"].is_(None),
            ),
        )
        .order_by(SyncJob.sync_id, SyncJob.created_at.desc())
    )
    vespa_job_result = await db.execute(arf_to_vespa_job_query)
    vespa_job_rows = list(vespa_job_result)

    # Build map of sync_id -> most recent Vespa job (first per sync_id due to ordering)
    vespa_job_map = {}
    for row in vespa_job_rows:
        if row.sync_id not in vespa_job_map:
            vespa_job_map[row.sync_id] = {
                "id": row.id,
                "status": row.status,
                "created_at": row.created_at,
                "completed_at": row.completed_at,
                "config": row.sync_config,
            }
    timings["vespa_job_info"] = (time.monotonic() - vespa_job_start) * 1000

    # Build response using helper function
    build_start = time.monotonic()
    admin_syncs = _build_admin_sync_info_list(
        syncs=syncs,
        sync_connections=sync_connections,
        source_conn_map=source_conn_map,
        last_job_map=last_job_map,
        vespa_job_map=vespa_job_map,
        entity_count_map=entity_count_map,
        arf_count_map=arf_count_map,
        qdrant_count_map=qdrant_count_map,
        vespa_count_map=vespa_count_map,
    )
    timings["build_response"] = (time.monotonic() - build_start) * 1000
    timings["total"] = (time.monotonic() - request_start) * 1000

    ctx.logger.info(
        f"Admin listed {len(admin_syncs)} syncs in {timings['total']:.1f}ms "
        f"(query={timings['main_query']:.1f}ms, "
        f"entity_counts={timings['entity_counts']:.1f}ms, "
        f"arf_counts={timings['arf_counts']:.1f}ms, "
        f"last_job={timings['last_job_info']:.1f}ms, "
        f"source_conn={timings['source_connections']:.1f}ms, "
        f"dest_counts={timings['destination_counts']:.1f}ms, "
        f"sync_conn={timings['sync_connections']:.1f}ms, "
        f"vespa_job={timings['vespa_job_info']:.1f}ms, "
        f"build={timings['build_response']:.1f}ms) | "
        f"filters: sync_ids={len(parsed_sync_ids) if parsed_sync_ids else 0}, "
        f"org={organization_id}, collection={collection_id}, "
        f"source={source_type}, status={status}, "
        f"last_job_status={last_job_status}, "
        f"has_source={has_source_connection}, "
        f"is_authenticated={is_authenticated}, "
        f"vespa_status={last_vespa_job_status}, "
        f"has_vespa_job={has_vespa_job}, "
        f"ghost_syncs_n={ghost_syncs_last_n}, "
        f"include_arf_counts={include_arf_counts}, "
        f"include_destination_counts={include_destination_counts}"
    )

    return admin_syncs


async def _fetch_destination_counts(
    syncs: list, source_conn_map: dict, ctx: ApiContext
) -> tuple[dict, dict]:
    """Fetch document counts from Qdrant and Vespa for given syncs.

    This is expensive as it queries each destination. Use sparingly.

    Args:
        syncs: List of Sync objects
        source_conn_map: Map of sync_id to source connection info (includes collection_id)
        ctx: API context

    Returns:
        Tuple of (qdrant_count_map, vespa_count_map)
    """
    import asyncio
    from uuid import UUID

    from airweave.core.config import settings
    from airweave.platform.destinations.qdrant import QdrantDestination
    from airweave.platform.destinations.vespa import VespaDestination

    qdrant_count_map = {}
    vespa_count_map = {}

    # Limit concurrent queries per destination to avoid overwhelming them
    MAX_CONCURRENT_COUNTS = 20

    # Group syncs by collection_id for efficiency
    syncs_by_collection = {}
    for sync in syncs:
        source_info = source_conn_map.get(sync.id, {})
        coll_id = source_info.get("collection_id")
        if not coll_id:
            # No collection for this sync, skip
            qdrant_count_map[sync.id] = None
            vespa_count_map[sync.id] = None
            continue

        if coll_id not in syncs_by_collection:
            syncs_by_collection[coll_id] = []
        syncs_by_collection[coll_id].append(sync)

    # Process all collections in parallel
    async def process_collection(collection_id, collection_syncs):
        """Process Qdrant and Vespa counts for a collection in parallel."""
        qdrant_results = {}
        vespa_results = {}

        # Define Qdrant counting function
        async def count_qdrant():
            try:
                qdrant = await QdrantDestination.create(
                    collection_id=collection_id,
                    organization_id=collection_syncs[0].organization_id,
                    logger=ctx.logger,
                )

                # Semaphore to limit concurrent queries
                semaphore = asyncio.Semaphore(MAX_CONCURRENT_COUNTS)

                # Parallelize all sync counts for this collection (with limit)
                async def count_qdrant_sync(sync):
                    async with semaphore:
                        try:
                            from qdrant_client.models import FieldCondition, Filter, MatchValue

                            scroll_filter = Filter(
                                must=[
                                    FieldCondition(
                                        key="airweave_system_metadata.sync_id",
                                        match=MatchValue(value=str(sync.id)),
                                    )
                                ]
                            )

                            count_result = await qdrant.client.count(
                                collection_name=qdrant.collection_name,
                                count_filter=scroll_filter,
                                exact=True,
                            )
                            return sync.id, count_result.count
                        except Exception as e:
                            ctx.logger.warning(
                                f"Failed to count Qdrant docs for sync {sync.id}: {e}"
                            )
                            return sync.id, None

                # Run all Qdrant counts in parallel (limited to MAX_CONCURRENT_COUNTS)
                results = await asyncio.gather(
                    *[count_qdrant_sync(sync) for sync in collection_syncs]
                )
                return {sync_id: count for sync_id, count in results}

            except Exception as e:
                ctx.logger.warning(
                    f"Failed to create Qdrant destination for collection {collection_id}: {e}"
                )
                return {sync.id: None for sync in collection_syncs}

        # Define Vespa counting function
        async def count_vespa():
            try:
                vespa = await VespaDestination.create(
                    collection_id=collection_id,
                    organization_id=collection_syncs[0].organization_id,
                    logger=ctx.logger,
                )

                # Semaphore to limit concurrent queries
                semaphore = asyncio.Semaphore(MAX_CONCURRENT_COUNTS)

                # Parallelize all sync counts for this collection (with limit)
                async def count_vespa_sync(sync):
                    async with semaphore:
                        try:
                            yql = (
                                f"select * from base_entity "
                                f"where airweave_system_metadata_sync_id contains '{sync.id}' "
                                f"and airweave_system_metadata_collection_id contains '{collection_id}' "
                                f"limit 0"
                            )

                            query_params = {"yql": yql}
                            response = await asyncio.to_thread(vespa.app.query, body=query_params)

                            if response.is_successful():
                                count = (
                                    response.json.get("root", {})
                                    .get("fields", {})
                                    .get("totalCount", 0)
                                )
                                return sync.id, count
                            else:
                                error_msg = response.json.get("root", {}).get("errors", [])
                                ctx.logger.warning(
                                    f"Vespa query failed for sync {sync.id}: {error_msg}"
                                )
                                return sync.id, None
                        except Exception as e:
                            ctx.logger.warning(
                                f"Failed to count Vespa docs for sync {sync.id}: {e}"
                            )
                            return sync.id, None

                # Run all Vespa counts in parallel (limited to MAX_CONCURRENT_COUNTS)
                results = await asyncio.gather(
                    *[count_vespa_sync(sync) for sync in collection_syncs]
                )
                return {sync_id: count for sync_id, count in results}

            except Exception as e:
                ctx.logger.warning(
                    f"Failed to create Vespa destination for collection {collection_id}: {e}"
                )
                return {sync.id: None for sync in collection_syncs}

        # Run Qdrant and Vespa in parallel for this collection
        qdrant_results, vespa_results = await asyncio.gather(
            count_qdrant(), count_vespa(), return_exceptions=False
        )

        return qdrant_results, vespa_results

    # Process all collections in parallel
    collection_tasks = [
        process_collection(coll_id, coll_syncs)
        for coll_id, coll_syncs in syncs_by_collection.items()
    ]
    collection_results = await asyncio.gather(*collection_tasks, return_exceptions=True)

    # Merge results from all collections
    for result in collection_results:
        if isinstance(result, Exception):
            ctx.logger.error(f"Collection processing failed: {result}")
            continue
        qdrant_results, vespa_results = result
        qdrant_count_map.update(qdrant_results)
        vespa_count_map.update(vespa_results)

    return qdrant_count_map, vespa_count_map


def _build_admin_sync_info_list(
    syncs: list,
    sync_connections: dict,
    source_conn_map: dict,
    last_job_map: dict,
    vespa_job_map: dict,
    entity_count_map: dict,
    arf_count_map: dict,
    qdrant_count_map: dict,
    vespa_count_map: dict,
) -> List[AdminSyncInfo]:
    """Build list of AdminSyncInfo from query results."""
    admin_syncs = []
    for sync in syncs:
        conn_info = sync_connections.get(sync.id, {"source": None, "destinations": []})
        source_info = source_conn_map.get(sync.id, {})
        last_job = last_job_map.get(sync.id, {})
        vespa_job = vespa_job_map.get(sync.id, {})

        sync_dict = {**sync.__dict__}
        if "_sa_instance_state" in sync_dict:
            sync_dict.pop("_sa_instance_state")

        sync_dict["source_connection_id"] = conn_info["source"]
        sync_dict["destination_connection_ids"] = conn_info["destinations"]
        sync_dict["total_entity_count"] = entity_count_map.get(sync.id, 0)
        sync_dict["total_arf_entity_count"] = arf_count_map.get(sync.id)
        sync_dict["total_qdrant_entity_count"] = qdrant_count_map.get(sync.id)
        sync_dict["total_vespa_entity_count"] = vespa_count_map.get(sync.id)
        # Handle status - may be enum or string depending on query
        last_status = last_job.get("status")
        sync_dict["last_job_status"] = (
            (last_status.value if hasattr(last_status, "value") else last_status)
            if last_status
            else None
        )
        sync_dict["last_job_at"] = last_job.get("completed_at")
        sync_dict["last_job_error"] = last_job.get("error")
        sync_dict["source_short_name"] = source_info.get("short_name")
        sync_dict["readable_collection_id"] = source_info.get("readable_collection_id")
        sync_dict["source_is_authenticated"] = source_info.get("is_authenticated")

        # Vespa migration tracking
        sync_dict["last_vespa_job_id"] = vespa_job.get("id")
        vespa_status = vespa_job.get("status")
        sync_dict["last_vespa_job_status"] = (
            (vespa_status.value if hasattr(vespa_status, "value") else vespa_status)
            if vespa_status
            else None
        )
        # Use completed_at if job is completed, otherwise use created_at for running/pending jobs
        if vespa_job.get("completed_at"):
            sync_dict["last_vespa_job_at"] = vespa_job.get("completed_at")
        else:
            sync_dict["last_vespa_job_at"] = vespa_job.get("created_at")
        sync_dict["last_vespa_job_config"] = vespa_job.get("config")

        admin_syncs.append(AdminSyncInfo.model_validate(sync_dict))

    return admin_syncs


@router.post("/sync-jobs/{job_id}/cancel", response_model=schemas.SyncJob)
async def admin_cancel_sync_job(
    job_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.SyncJob:
    """Admin-only: Cancel any sync job regardless of organization.

    This endpoint allows admins or API keys with `api_key_admin_sync` permission
    to cancel sync jobs across organizations for migration and support purposes.

    Args:
        job_id: The ID of the sync job to cancel
        db: Database session
        ctx: API context

    Returns:
        The updated sync job

    Raises:
        HTTPException: If not admin, job not found, or job not cancellable
    """
    from sqlalchemy import select as sa_select

    from airweave.core.datetime_utils import utc_now_naive
    from airweave.core.shared_models import SyncJobStatus
    from airweave.core.sync_job_service import sync_job_service
    from airweave.core.temporal_service import temporal_service
    from airweave.models.sync_job import SyncJob

    _require_admin_permission(ctx, FeatureFlagEnum.API_KEY_ADMIN_SYNC)

    # Get the sync job without organization filtering
    result = await db.execute(sa_select(SyncJob).where(SyncJob.id == job_id))
    sync_job = result.scalar_one_or_none()

    if not sync_job:
        raise NotFoundException(f"Sync job {job_id} not found")

    ctx.logger.info(
        f"Admin cancelling sync job {job_id} (org: {sync_job.organization_id}, "
        f"status: {sync_job.status})"
    )

    # Check if job is in a cancellable state (handle status as string or enum)
    job_status_str = sync_job.status.value if hasattr(sync_job.status, "value") else sync_job.status
    if job_status_str not in [SyncJobStatus.PENDING.value, SyncJobStatus.RUNNING.value]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job in {job_status_str} state",
        )

    # Set transitional status to CANCELLING immediately
    await sync_job_service.update_status(
        sync_job_id=job_id,
        status=SyncJobStatus.CANCELLING,
        ctx=ctx,
    )

    # Fire-and-forget cancellation request to Temporal
    cancel_result = await temporal_service.cancel_sync_job_workflow(str(job_id), ctx)

    if not cancel_result["success"]:
        # Actual Temporal connectivity/availability error - revert status
        fallback_status = (
            SyncJobStatus.RUNNING
            if sync_job.status == SyncJobStatus.RUNNING
            else SyncJobStatus.PENDING
        )
        await sync_job_service.update_status(
            sync_job_id=job_id,
            status=fallback_status,
            ctx=ctx,
        )
        raise HTTPException(status_code=502, detail="Failed to request cancellation from Temporal")

    # If workflow wasn't found, mark job as CANCELLED directly
    if not cancel_result["workflow_found"]:
        ctx.logger.info(f"Workflow not found for job {job_id} - marking as CANCELLED directly")
        await sync_job_service.update_status(
            sync_job_id=job_id,
            status=SyncJobStatus.CANCELLED,
            ctx=ctx,
            completed_at=utc_now_naive(),
            error="Workflow not found in Temporal - may have already completed",
        )

    # Fetch the updated job from database
    await db.refresh(sync_job)

    ctx.logger.info(f"✅ Admin cancelled sync job {job_id}, new status: {sync_job.status}")

    return schemas.SyncJob.model_validate(sync_job, from_attributes=True)


@router.post("/syncs/{sync_id}/cancel")
async def admin_cancel_sync_by_id(
    sync_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> dict:
    """Admin-only: Cancel all pending/running jobs for a sync.
    This is a convenience endpoint that finds active jobs for a sync and cancels them.
    More practical than /sync-jobs/{job_id}/cancel when you know the sync ID.
    Args:
        sync_id: The sync ID whose jobs should be cancelled
        db: Database session
        ctx: API context
    Returns:
        Dict with cancelled job IDs and results
    Raises:
        HTTPException: If not admin or sync not found
    """
    from sqlalchemy import select as sa_select

    from airweave.core.datetime_utils import utc_now_naive
    from airweave.core.shared_models import SyncJobStatus
    from airweave.core.sync_job_service import sync_job_service
    from airweave.core.temporal_service import temporal_service
    from airweave.models.sync import Sync
    from airweave.models.sync_job import SyncJob

    _require_admin_permission(ctx, FeatureFlagEnum.API_KEY_ADMIN_SYNC)

    # Verify sync exists
    result = await db.execute(sa_select(Sync).where(Sync.id == sync_id))
    sync_obj = result.scalar_one_or_none()
    if not sync_obj:
        raise NotFoundException(f"Sync {sync_id} not found")

    # Find all pending/running jobs
    jobs_result = await db.execute(
        sa_select(SyncJob).where(
            SyncJob.sync_id == sync_id,
            SyncJob.status.in_([SyncJobStatus.PENDING, SyncJobStatus.RUNNING]),
        )
    )
    jobs = list(jobs_result.scalars().all())

    if not jobs:
        return {
            "sync_id": str(sync_id),
            "message": "No active jobs to cancel",
            "cancelled_jobs": [],
        }

    ctx.logger.info(f"Admin cancelling {len(jobs)} active job(s) for sync {sync_id}")

    cancelled_jobs = []
    failed_jobs = []

    for job in jobs:
        job_id = job.id
        job_status_str = job.status.value if hasattr(job.status, "value") else job.status

        try:
            # Set to CANCELLING
            await sync_job_service.update_status(
                sync_job_id=job_id,
                status=SyncJobStatus.CANCELLING,
                ctx=ctx,
            )

            # Request cancellation from Temporal
            cancel_result = await temporal_service.cancel_sync_job_workflow(str(job_id), ctx)

            if not cancel_result["success"]:
                # Temporal error - revert status
                fallback_status = (
                    SyncJobStatus.RUNNING
                    if job.status == SyncJobStatus.RUNNING
                    else SyncJobStatus.PENDING
                )
                await sync_job_service.update_status(
                    sync_job_id=job_id,
                    status=fallback_status,
                    ctx=ctx,
                )
                failed_jobs.append(
                    {
                        "job_id": str(job_id),
                        "error": "Failed to request cancellation from Temporal",
                    }
                )
                continue

            # If workflow not found, mark as CANCELLED directly
            if not cancel_result["workflow_found"]:
                ctx.logger.info(f"Workflow not found for job {job_id} - marking as CANCELLED")
                await sync_job_service.update_status(
                    sync_job_id=job_id,
                    status=SyncJobStatus.CANCELLED,
                    ctx=ctx,
                    completed_at=utc_now_naive(),
                    error="Workflow not found in Temporal - may have already completed",
                )

            cancelled_jobs.append(
                {
                    "job_id": str(job_id),
                    "previous_status": job_status_str,
                    "workflow_found": cancel_result["workflow_found"],
                }
            )

        except Exception as e:
            ctx.logger.error(f"Failed to cancel job {job_id}: {e}")
            failed_jobs.append({"job_id": str(job_id), "error": str(e)})

    ctx.logger.info(
        f"✅ Admin cancelled {len(cancelled_jobs)}/{len(jobs)} job(s) for sync {sync_id}"
    )

    return {
        "sync_id": str(sync_id),
        "total_jobs": len(jobs),
        "cancelled": len(cancelled_jobs),
        "failed": len(failed_jobs),
        "cancelled_jobs": cancelled_jobs,
        "failed_jobs": failed_jobs,
    }


@router.delete("/syncs/{sync_id}")
async def admin_delete_sync(
    sync_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> dict:
    """Admin-only: Delete a sync and all related data.

    This endpoint reuses the existing source connection deletion logic which handles:
    - Cancelling active jobs
    - Cleaning up Temporal schedules
    - Removing data from Qdrant
    - Removing data from Vespa
    - Removing ARF storage
    - Cascading deletes in Postgres (sync, connection, source_connection)

    Args:
        sync_id: The sync ID to delete
        db: Database session
        ctx: API context

    Returns:
        Success message with deleted sync ID

    Raises:
        HTTPException: If not admin, sync not found, or deletion fails
    """
    from sqlalchemy import select as sa_select

    from airweave.core.source_connection_service import source_connection_service
    from airweave.models.source_connection import SourceConnection
    from airweave.models.sync import Sync

    _require_admin_permission(ctx, FeatureFlagEnum.API_KEY_ADMIN_SYNC)

    # Verify sync exists
    result = await db.execute(sa_select(Sync).where(Sync.id == sync_id))
    sync_obj = result.scalar_one_or_none()
    if not sync_obj:
        raise NotFoundException(f"Sync {sync_id} not found")

    # Find the source connection for this sync
    source_conn_result = await db.execute(
        sa_select(SourceConnection).where(SourceConnection.sync_id == sync_id)
    )
    source_conn = source_conn_result.scalar_one_or_none()

    if not source_conn:
        raise NotFoundException(f"Source connection not found for sync {sync_id}")

    ctx.logger.info(
        f"Admin deleting sync {sync_id} (org: {sync_obj.organization_id}) "
        f"via source connection {source_conn.id}"
    )

    # Build context for the sync's organization
    sync_org_ctx = await _build_org_context(db, sync_obj.organization_id, ctx)

    # Use the existing source connection delete logic which handles all cleanup
    try:
        await source_connection_service.delete(
            db,
            id=source_conn.id,
            ctx=sync_org_ctx,
        )

        ctx.logger.info(f"✅ Admin successfully deleted sync {sync_id}")

        return {
            "sync_id": str(sync_id),
            "message": "Sync deleted successfully",
            "deleted_source_connection_id": str(source_conn.id),
        }
    except Exception as e:
        ctx.logger.error(f"Failed to delete sync {sync_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete sync: {str(e)}")
